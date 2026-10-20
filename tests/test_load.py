"""Release loads: idempotence, ordering, and recovery from an interrupted refresh."""

from __future__ import annotations

import gzip
import hashlib
import random
from pathlib import Path
from typing import Any

import pytest

from clinvar_history import load
from clinvar_history.config import Paths
from clinvar_history.db import Engine, migrate
from clinvar_history.fetch import record
from clinvar_history.sources import clinvar, gnomad
from clinvar_history.validate import run_checks

from .conftest import DATA

TABLES = [
    "source_release",
    "provenance",
    "gene",
    "clinvar_variation",
    "clinvar_variation_history",
    "classification",
    "submitter",
    "submission",
]


def snapshot(engine: Engine) -> dict[str, Any]:
    """Full contents of every release-scoped table, in a stable order."""
    out: dict[str, Any] = {}
    for table in TABLES:
        cols, _ = engine.query(f"SELECT * FROM {table} LIMIT 0")
        order = ", ".join(str(i + 1) for i in range(len(cols)))
        out[table] = engine.query(f"SELECT * FROM {table} ORDER BY {order}")[1]
    return out


def test_counts_after_two_releases(loaded_engine: Engine) -> None:
    assert loaded_engine.scalar("SELECT count(*) FROM clinvar_variation") == 10
    # 7 versions from 2025-10, then V1 and V4 changed and V8, V9, V10 arrived.
    assert loaded_engine.scalar("SELECT count(*) FROM classification") == 12
    assert loaded_engine.scalar("SELECT count(*) FROM classification WHERE is_current") == 9
    # V6 left ClinVar: its only version is closed by the 2026-10 release.
    assert (
        loaded_engine.scalar(
            "SELECT count(*) FROM classification WHERE variation_id = 1006 AND is_current"
        )
        == 0
    )
    # 15 rows in the 2026-10 file: one repeated SCV is dropped at staging and one
    # orphan VariationID at load, leaving 13.
    assert (
        loaded_engine.scalar(
            "SELECT count(*) FROM submission AS s INNER JOIN v_clinvar_release AS r"
            " ON s.release_id = r.release_id AND r.recency_rank = 1"
        )
        == 13
    )


def test_validation_passes(loaded_engine: Engine) -> None:
    failed = [r for r in run_checks(loaded_engine) if not r.passed]
    assert failed == []


def test_reload_is_a_no_op(empty_engine: Engine, fixture_paths: Paths) -> None:
    migrate(empty_engine)
    assert load.load_clinvar(empty_engine, fixture_paths, "2025-10") is True
    before = snapshot(empty_engine)
    assert load.load_clinvar(empty_engine, fixture_paths, "2025-10") is False
    assert snapshot(empty_engine) == before


def test_releases_load_oldest_first(empty_engine: Engine, fixture_paths: Paths) -> None:
    migrate(empty_engine)
    load.load_clinvar(empty_engine, fixture_paths, "2026-10")
    with pytest.raises(load.LoadError, match="oldest first"):
        load.load_clinvar(empty_engine, fixture_paths, "2025-10")


@pytest.mark.parametrize(
    "step",
    ["release", "clinvar_variation", "classification_close", "classification_open", "submission"],
)
def test_drill_interrupted_refresh_rolls_back(
    empty_engine: Engine, fixture_paths: Paths, step: str
) -> None:
    """Drill: crash the 2026-10 refresh at each step and check nothing half-applied stays."""
    migrate(empty_engine)
    load.load_clinvar(empty_engine, fixture_paths, "2025-10")
    before = snapshot(empty_engine)

    def crash(at: str) -> None:
        if at == step:
            raise RuntimeError(f"simulated failure after {at}")

    with pytest.raises(RuntimeError, match="simulated failure"):
        load.load_clinvar(empty_engine, fixture_paths, "2026-10", step_hook=crash)
    assert snapshot(empty_engine) == before
    # The previous release is still the one analysts see.
    assert (
        empty_engine.scalar("SELECT label FROM v_clinvar_release WHERE recency_rank = 1")
        == "2025-10"
    )
    assert empty_engine.scalar("SELECT count(*) FROM v_variant_current") == 7
    # The retry starts from a clean state and completes.
    assert load.load_clinvar(empty_engine, fixture_paths, "2026-10") is True
    assert empty_engine.scalar("SELECT count(*) FROM classification WHERE is_current") == 9


def test_unload_restores_previous_release(empty_engine: Engine, fixture_paths: Paths) -> None:
    migrate(empty_engine)
    load.load_clinvar(empty_engine, fixture_paths, "2025-10")
    before = snapshot(empty_engine)
    load.load_clinvar(empty_engine, fixture_paths, "2026-10")
    # 2026-10 rewrote V3's transcript (NM_000546.6 -> .7) in place.
    assert (
        empty_engine.scalar("SELECT transcript FROM clinvar_variation WHERE variation_id = 1003")
        == "NM_000546.7"
    )
    assert empty_engine.scalar("SELECT count(*) FROM clinvar_variation_history") == 1
    assert load.unload_latest_clinvar(empty_engine) == "2026-10"
    after = snapshot(empty_engine)
    # Row for row, every table matches its state before 2026-10, except that the
    # release row stays as 'rolled_back' and submitters first seen in 2026-10
    # stay (they are names, not assertions).
    for key in ("submitter", "source_release"):
        after.pop(key)
        before.pop(key)
    assert after == before
    assert (
        empty_engine.scalar("SELECT status FROM source_release WHERE label = '2026-10'")
        == "rolled_back"
    )
    # Loading the same release again reuses the audit row and succeeds.
    assert load.load_clinvar(empty_engine, fixture_paths, "2026-10") is True


def test_changed_file_is_refused(empty_engine: Engine, fixture_paths: Paths) -> None:
    migrate(empty_engine)
    load.load_clinvar(empty_engine, fixture_paths, "2025-10")
    empty_engine.execute("UPDATE provenance SET sha256 = repeat('0', 64)")
    with pytest.raises(load.LoadError, match="different files"):
        load.load_clinvar(empty_engine, fixture_paths, "2025-10")


def test_changed_gnomad_file_is_refused_without_a_missing_command(
    empty_engine: Engine, fixture_paths: Paths
) -> None:
    # unload works only for the latest ClinVar release, so the message must not offer it
    migrate(empty_engine)
    for release in ("2025-10", "2026-10"):
        load.load_clinvar(empty_engine, fixture_paths, release)
    load.load_panel(empty_engine, fixture_paths)
    load.load_gnomad(empty_engine, fixture_paths, "4.1")
    empty_engine.execute("UPDATE provenance SET sha256 = repeat('0', 64)")
    with pytest.raises(load.LoadError, match="different files") as refused:
        load.load_gnomad(empty_engine, fixture_paths, "4.1")
    assert "unload" not in str(refused.value)


def test_mavedb_load_without_files_is_skipped(empty_engine: Engine, tmp_path: Path) -> None:
    migrate(empty_engine)
    assert load.load_mavedb(empty_engine, Paths(tmp_path)) is False
    assert empty_engine.scalar("SELECT count(*) FROM score_set") == 0


def test_allele_longer_than_a_btree_row_loads(empty_engine: Engine, tmp_path: Path) -> None:
    # A PostgreSQL B-tree row holds at most 2704 bytes, and the longest ClinVar
    # alleles pass it (#1). Random bases from one generator, so compression
    # cannot bring the key under.
    rng = random.Random(1)
    ref = "".join(rng.choice("ACGT") for _ in range(10_000))
    key = f"13-32315000-{ref}-{ref[0]}"
    paths = Paths(tmp_path)
    dest = paths.raw / "gnomad" / "gnomad.joint.v4.1.LONG.vcf.gz"
    dest.parent.mkdir(parents=True)
    info = "AC_joint=1;AN_joint=10000;AF_joint=0.0001;nhomalt_joint=0"
    with gzip.open(dest, "wt") as fh:
        fh.write("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        fh.write(f"chr13\t32315000\t.\t{ref}\t{ref[0]}\t.\tPASS\t{info}\n")
    record(paths, source="gnomad", release="4.1", url="fixture://long", path=dest, method="fixture")
    gnomad.stage(paths.raw / "gnomad", paths.staging, [], "4.1")
    migrate(empty_engine)
    assert load.load_gnomad(empty_engine, paths, "4.1") is True
    _, rows = empty_engine.query("SELECT variant_key, variant_class FROM variant")
    assert rows == [(key, "deletion")]
    assert empty_engine.scalar("SELECT count(*) FROM population_frequency") == 1
    digest = hashlib.md5(key.encode()).hexdigest()
    assert empty_engine.scalar("SELECT variant_key_md5 FROM variant") == digest


def test_moved_allele_rekeys_the_variation(empty_engine: Engine, tmp_path: Path) -> None:
    # ClinVar can correct a variation's VCF position between releases. The load
    # must point the variation at the new variant row, and the unload back at
    # the old one, so both UPDATEs have to rewrite variant_key_md5 (0008).
    lines = (DATA / "variant_summary_2025-10.tsv").read_text().splitlines(keepends=True)
    header = lines[0].rstrip("\n").split("\t")
    vid, asm, pos = (header.index(c) for c in ("VariationID", "Assembly", "PositionVCF"))
    moved = []
    for line in lines:
        fields = line.rstrip("\n").split("\t")
        if fields[vid] == "1003" and fields[asm] == "GRCh38":
            fields[pos] = "7675089"
            line = "\t".join(fields) + "\n"
        moved.append(line)
    subs = (DATA / "submission_summary_2025-10.tsv").read_text()
    paths = Paths(tmp_path)
    for release, variants in (("2025-10", "".join(lines)), ("2026-10", "".join(moved))):
        for kind, text in (("variant_summary", variants), ("submission_summary", subs)):
            dest = paths.raw / "clinvar" / f"{kind}_{release}.txt.gz"
            dest.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(dest, "wt") as fh:
                fh.write(text)
            record(
                paths,
                source="clinvar",
                release=release,
                url=f"fixture://{dest.name}",
                path=dest,
                method="fixture",
            )
        clinvar.stage_release(paths.raw / "clinvar", paths.staging, release)

    def v3() -> list[Any]:
        sql = "SELECT variant_key, variant_key_md5 FROM clinvar_variation WHERE variation_id = 1003"
        return empty_engine.query(sql)[1]

    old, new = "17-7675088-C-T", "17-7675089-C-T"
    migrate(empty_engine)
    load.load_clinvar(empty_engine, paths, "2025-10")
    assert v3() == [(old, hashlib.md5(old.encode()).hexdigest())]
    load.load_clinvar(empty_engine, paths, "2026-10")
    assert v3() == [(new, hashlib.md5(new.encode()).hexdigest())]
    joined = (
        "SELECT v.variant_key FROM clinvar_variation AS cv INNER JOIN variant AS v"
        " ON cv.variant_key_md5 = v.variant_key_md5 WHERE cv.variation_id = 1003"
    )
    assert empty_engine.scalar(joined) == new
    assert load.unload_latest_clinvar(empty_engine) == "2026-10"
    assert v3() == [(old, hashlib.md5(old.encode()).hexdigest())]
    assert empty_engine.scalar(joined) == old
