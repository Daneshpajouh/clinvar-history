"""Load staged Parquet into the warehouse, one source release per transaction.

A ClinVar release load either commits completely or leaves the database as it
was: the release row, the SCD type 2 classification changes, submissions and
provenance are written inside one transaction. Re-running a load whose files
match the recorded SHA-256 values is a no-op.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vwh.config import Paths
from vwh.db import Engine
from vwh.fetch import read_manifest
from vwh.logs import get_logger

log = get_logger(__name__)

# Test hook: called with a step name; raising from it simulates a crash mid-load.
StepHook = Callable[[str], None]


class LoadError(RuntimeError):
    pass


def _noop(_step: str) -> None:
    return None


def _manifest_rows(paths: Paths, source: str, release: str) -> list[dict[str, Any]]:
    return [r for r in read_manifest(paths) if r["source"] == source and r["release"] == release]


def _release_state(engine: Engine, source: str, label: str) -> tuple[int | None, dict[str, str]]:
    _, rows = engine.query(
        "SELECT release_id FROM source_release WHERE source = ? AND label = ? AND status = 'loaded'",
        [source, label],
    )
    if not rows:
        return None, {}
    rid = int(rows[0][0])
    _, prov = engine.query("SELECT local_path, sha256 FROM provenance WHERE release_id = ?", [rid])
    return rid, {p: s for p, s in prov}


def _already_loaded(engine: Engine, source: str, label: str, files: list[dict[str, Any]]) -> bool:
    rid, recorded = _release_state(engine, source, label)
    if rid is None:
        return False
    wanted = {f["path"]: f["sha256"] for f in files}
    if wanted and wanted != recorded:
        raise LoadError(
            f"{source} {label} is loaded from different files; run 'vwh unload {source}' first"
        )
    log.info("already loaded, skipping", extra={"source": source, "release": label})
    return True


def _new_release(engine: Engine, source: str, label: str, release_date: str | None) -> int:
    old = engine.scalar(
        "SELECT release_id FROM source_release WHERE source = ? AND label = ?"
        " AND status = 'rolled_back'",
        [source, label],
    )
    if old is not None:
        engine.execute("UPDATE source_release SET status = 'loading' WHERE release_id = ?", [old])
        return int(old)
    engine.execute(
        "INSERT INTO source_release (source, label, release_date, status) VALUES (?, ?, ?, 'loading')",
        [source, label, release_date],
    )
    return int(
        engine.scalar(
            "SELECT release_id FROM source_release WHERE source = ? AND label = ?", [source, label]
        )
    )


def _finish_release(
    engine: Engine, rid: int, files: list[dict[str, Any]], counts: dict[str, tuple[int, int]]
) -> None:
    now = dt.datetime.now(dt.UTC).isoformat()
    for f in files:
        staged, loaded = counts.get(Path(f["path"]).name, (None, None))
        engine.execute(
            "INSERT INTO provenance (release_id, url, local_path, size_bytes, sha256, fetched_at,"
            " loaded_at, rows_staged, rows_loaded, terms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [rid, f["url"], f["path"], f["size_bytes"], f["sha256"], f["fetched_at"], now,
             staged, loaded, f["terms"]],
        )  # fmt: skip
    engine.execute(
        "UPDATE source_release SET status = 'loaded', loaded_at = ? WHERE release_id = ?", [now, rid]
    )


def _in_transaction(engine: Engine, body: Callable[[], None]) -> None:
    engine.begin()
    try:
        body()
        engine.commit()
    except BaseException:
        engine.rollback()
        raise


# ---------------------------------------------------------------- ClinVar


def load_clinvar(
    engine: Engine, paths: Paths, release: str, *, step_hook: StepHook = _noop
) -> bool:
    files = _manifest_rows(paths, "clinvar", release)
    if _already_loaded(engine, "clinvar", release, files):
        return False
    newer = engine.scalar(
        "SELECT max(label) FROM source_release WHERE source = 'clinvar' AND status = 'loaded'"
        " AND label > ?",
        [release],
    )
    if newer:
        raise LoadError(f"ClinVar {newer} is already loaded; releases must load oldest first")
    stage_dir = paths.staging / "clinvar" / release
    n_var = engine.stage_parquet("stg_variants", stage_dir / "variants.parquet")
    n_sub = engine.stage_parquet("stg_submissions", stage_dir / "submissions.parquet")

    def body() -> None:
        rid = _new_release(engine, "clinvar", release, f"{release}-01")
        step_hook("release")
        engine.execute(
            "INSERT INTO gene (gene_id, symbol, hgnc_id)"
            " SELECT gene_id, min(gene_symbol), min(hgnc_id) FROM stg_variants"
            " WHERE gene_id IS NOT NULL GROUP BY gene_id"
            " ON CONFLICT (gene_id) DO UPDATE SET symbol = excluded.symbol, hgnc_id = excluded.hgnc_id"
        )
        engine.execute(
            "INSERT INTO variant (variant_key, chrom, pos, ref, alt, variant_class)"
            " SELECT DISTINCT variant_key, chrom, pos, ref, alt, variant_class FROM stg_variants"
            " WHERE variant_key IS NOT NULL ON CONFLICT (variant_key) DO NOTHING"
        )
        step_hook("variant")
        engine.execute(
            "INSERT INTO clinvar_variation (variation_id, allele_id, variant_key, gene_id, name,"
            " variant_type, transcript, hgvs_c, protein_change, hgvs_c_key, hgvs_p_key,"
            " first_release_id, last_release_id)"
            " SELECT variation_id, allele_id, variant_key, gene_id, name, variant_type, transcript,"
            " hgvs_c, protein_change, hgvs_c_key, hgvs_p_key, ?, ? FROM stg_variants"
            " ON CONFLICT (variation_id) DO UPDATE SET allele_id = excluded.allele_id,"
            " variant_key = excluded.variant_key, gene_id = excluded.gene_id, name = excluded.name,"
            " variant_type = excluded.variant_type, transcript = excluded.transcript,"
            " hgvs_c = excluded.hgvs_c, protein_change = excluded.protein_change,"
            " hgvs_c_key = excluded.hgvs_c_key, hgvs_p_key = excluded.hgvs_p_key,"
            " last_release_id = excluded.last_release_id",
            [rid, rid],
        )
        step_hook("clinvar_variation")
        # SCD type 2: close the current version when the aggregate record
        # changed or the variation left ClinVar, then open new versions.
        engine.execute(
            "UPDATE classification SET valid_to_release_id = ?, is_current = FALSE"
            " WHERE is_current AND variation_id IN ("
            "  SELECT c.variation_id FROM classification AS c"
            "  LEFT JOIN stg_variants AS s ON s.variation_id = c.variation_id"
            "  WHERE c.is_current AND (s.variation_id IS NULL"
            "   OR s.clinical_significance IS DISTINCT FROM c.clinical_significance"
            "   OR s.review_status IS DISTINCT FROM c.review_status"
            "   OR s.number_submitters IS DISTINCT FROM c.number_submitters"
            "   OR s.last_evaluated IS DISTINCT FROM c.last_evaluated))",
            [rid],
        )
        step_hook("classification_close")
        engine.execute(
            "INSERT INTO classification (variation_id, clinical_significance, clinsig_class,"
            " review_status, number_submitters, last_evaluated, valid_from_release_id,"
            " valid_to_release_id, is_current)"
            " SELECT s.variation_id, s.clinical_significance, s.clinsig_class, s.review_status,"
            " s.number_submitters, s.last_evaluated, ?, NULL, TRUE FROM stg_variants AS s"
            " LEFT JOIN classification AS c ON c.variation_id = s.variation_id AND c.is_current"
            " WHERE c.variation_id IS NULL",
            [rid],
        )
        step_hook("classification_open")
        engine.execute(
            "INSERT INTO submitter (name) SELECT DISTINCT submitter FROM stg_submissions"
            " ON CONFLICT (name) DO NOTHING"
        )
        engine.execute(
            "INSERT INTO submission (release_id, scv, scv_version, variation_id, submitter_id,"
            " clinical_significance, clinsig_class, date_last_evaluated, review_status,"
            " collection_method, submitted_gene_symbol)"
            " SELECT ?, s.scv, s.scv_version, s.variation_id, su.submitter_id,"
            " s.clinical_significance, s.clinsig_class, s.date_last_evaluated, s.review_status,"
            " s.collection_method, s.submitted_gene_symbol FROM stg_submissions AS s"
            " INNER JOIN submitter AS su ON su.name = s.submitter"
            " INNER JOIN clinvar_variation AS cv ON cv.variation_id = s.variation_id",
            [rid],
        )
        step_hook("submission")
        loaded_sub = int(engine.scalar("SELECT count(*) FROM submission WHERE release_id = ?", [rid]))
        counts = {
            f"variant_summary_{release}.txt.gz": (n_var, n_var),
            f"submission_summary_{release}.txt.gz": (n_sub, loaded_sub),
        }
        _finish_release(engine, rid, files, counts)
        log.info(
            "clinvar loaded",
            extra={"release": release, "variations": n_var, "submissions_staged": n_sub,
                   "submissions_loaded": loaded_sub},
        )  # fmt: skip

    _in_transaction(engine, body)
    return True


def unload_latest_clinvar(engine: Engine) -> str | None:
    """Roll back the most recent ClinVar release, restoring the SCD state before it."""
    _, rows = engine.query(
        "SELECT release_id, label FROM v_clinvar_release WHERE recency_rank <= 2 ORDER BY recency_rank"
    )
    if not rows:
        return None
    rid, label = int(rows[0][0]), str(rows[0][1])
    prev = int(rows[1][0]) if len(rows) > 1 else None

    def body() -> None:
        engine.execute("DELETE FROM submission WHERE release_id = ?", [rid])
        engine.execute("DELETE FROM classification WHERE valid_from_release_id = ?", [rid])
        engine.execute(
            "UPDATE classification SET valid_to_release_id = NULL, is_current = TRUE"
            " WHERE valid_to_release_id = ?",
            [rid],
        )
        engine.execute("DELETE FROM clinvar_variation WHERE first_release_id = ?", [rid])
        if prev is not None:
            engine.execute(
                "UPDATE clinvar_variation SET last_release_id = ? WHERE last_release_id = ?",
                [prev, rid],
            )
        # variant rows stay: they are allele keys, not release data, and DuckDB
        # rejects deleting a parent row in the transaction that deleted its child.
        engine.execute("DELETE FROM provenance WHERE release_id = ?", [rid])
        engine.execute(
            "UPDATE source_release SET status = 'rolled_back' WHERE release_id = ?", [rid]
        )

    _in_transaction(engine, body)
    log.info("clinvar release unloaded", extra={"release": label})
    return label


# ---------------------------------------------------------------- panel genes


def load_panel(engine: Engine, paths: Paths) -> int:
    genes = json.loads((paths.raw / "ensembl" / "genes.json").read_text())

    def body() -> None:
        for g in genes:
            engine.execute(
                "UPDATE gene SET in_panel = TRUE, ensembl_id = ?, chrom = ?, start_pos = ?,"
                " end_pos = ? WHERE symbol = ?",
                [g["ensembl_id"], g["chrom"].removeprefix("chr"), g["start"], g["end"], g["symbol"]],
            )

    _in_transaction(engine, body)
    return int(engine.scalar("SELECT count(*) FROM gene WHERE in_panel"))


# ---------------------------------------------------------------- gnomAD


def load_gnomad(engine: Engine, paths: Paths, release: str) -> bool:
    files = _manifest_rows(paths, "gnomad", release)
    if _already_loaded(engine, "gnomad", release, files):
        return False
    n = engine.stage_parquet("stg_freq", paths.staging / "gnomad" / release / "frequencies.parquet")

    def body() -> None:
        rid = _new_release(engine, "gnomad", release, None)
        engine.execute(
            "INSERT INTO variant (variant_key, chrom, pos, ref, alt, variant_class)"
            " SELECT DISTINCT variant_key, chrom, pos, ref, alt,"
            "  CASE WHEN length(ref) = 1 AND length(alt) = 1 THEN 'snv'"
            "   WHEN length(ref) = length(alt) THEN 'mnv'"
            "   WHEN length(ref) = 1 AND substr(alt, 1, 1) = ref THEN 'insertion'"
            "   WHEN length(alt) = 1 AND substr(ref, 1, 1) = alt THEN 'deletion'"
            "   ELSE 'delins' END"
            " FROM stg_freq ON CONFLICT (variant_key) DO NOTHING"
        )
        engine.execute(
            "INSERT INTO population_frequency (variant_key, release_id, ancestry_group, ac, an, af,"
            " nhomalt, filter) SELECT variant_key, ?, ancestry_group, ac, an, af, nhomalt, filter"
            " FROM stg_freq",
            [rid],
        )
        loaded = int(
            engine.scalar("SELECT count(*) FROM population_frequency WHERE release_id = ?", [rid])
        )
        # Ten per-gene files feed one staged table, so counts are logged as a total.
        _finish_release(engine, rid, files, {})
        log.info("gnomad loaded", extra={"rows_staged": n, "rows_loaded": loaded})

    _in_transaction(engine, body)
    return True


# ---------------------------------------------------------------- MaveDB


def load_mavedb(engine: Engine, paths: Paths) -> bool:
    files = [r for r in read_manifest(paths) if r["source"] == "mavedb"]
    label = max(r["fetched_at"][:10] for r in files)
    if _already_loaded(engine, "mavedb", label, files):
        return False
    stage = paths.staging / "mavedb" / "current"
    n_sets = engine.stage_parquet("stg_sets", stage / "score_sets.parquet")
    n_scores = engine.stage_parquet("stg_scores", stage / "scores.parquet")

    def body() -> None:
        rid = _new_release(engine, "mavedb", label, label)
        engine.execute(
            "DELETE FROM functional_score WHERE score_set_urn IN (SELECT urn FROM stg_sets)"
        )
        engine.execute("DELETE FROM score_set WHERE urn IN (SELECT urn FROM stg_sets)")
        engine.execute(
            "INSERT INTO score_set (urn, release_id, title, gene_symbol, gene_id, licence, doi,"
            " published_date, num_variants, match_level, target_accession)"
            " SELECT s.urn, ?, s.title, s.gene_symbol, g.gene_id, s.licence, s.doi,"
            " s.published_date, s.num_variants, s.match_level, s.target_accession"
            " FROM stg_sets AS s LEFT JOIN gene AS g ON g.symbol = s.gene_symbol AND g.in_panel",
            [rid],
        )
        engine.execute(
            "INSERT INTO functional_score (variant_urn, score_set_urn, hgvs_nt, hgvs_pro, score,"
            " match_key) SELECT variant_urn, score_set_urn, hgvs_nt, hgvs_pro, score, match_key"
            " FROM stg_scores"
        )
        _finish_release(engine, rid, files, {})
        log.info("mavedb loaded", extra={"score_sets": n_sets, "scores": n_scores})

    _in_transaction(engine, body)
    return True
