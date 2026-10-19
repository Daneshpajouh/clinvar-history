"""Parse MaveDB score sets and build the keys used to match ClinVar variants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from clinvar_history.logs import get_logger
from clinvar_history.sources.clinvar import PROTEIN_SUB_RE

log = get_logger(__name__)


def score_set_row(meta: dict[str, Any], cfg_entry: dict[str, Any]) -> dict[str, Any]:
    target = meta["targetGenes"][0]
    accession = (target.get("targetAccession") or {}).get("accession")
    pubs = meta.get("primaryPublicationIdentifiers") or []
    return {
        "urn": meta["urn"],
        "title": meta["title"],
        "gene_symbol": cfg_entry["gene"],
        "licence": meta["license"]["shortName"],
        "doi": pubs[0].get("doi") if pubs else None,
        "published_date": meta.get("publishedDate"),
        "num_variants": meta.get("numVariants"),
        "match_level": cfg_entry["match_level"],
        "target_accession": accession,
    }


def match_keys(scores: pl.DataFrame, gene: str, level: str) -> pl.Expr:
    """Key that lines up with clinvar_variation.hgvs_c_key or hgvs_p_key.

    Nucleotide sets turn "NM_007294.3:c.5565A>T" into "NM_007294:c.5565A>T";
    the transcript version is dropped because ClinVar may cite a newer version
    of the same transcript. Protein sets give "TP53:p.Arg175His"; only single
    amino acid substitutions, nonsense and synonymous changes get a key.
    """
    if level == "nucleotide":
        parts = pl.col("hgvs_nt").str.extract_groups(r"^(?<tx>N[MR]_\d+)\.\d+:(?<c>c\..+)$")
        return pl.concat_str([parts.struct.field("tx"), parts.struct.field("c")], separator=":")
    return (
        pl.when(pl.col("hgvs_pro").str.contains(PROTEIN_SUB_RE))
        .then(pl.lit(f"{gene}:") + pl.col("hgvs_pro"))
        .otherwise(None)
    )


def stage(raw_dir: Path, staging_dir: Path, score_sets: list[dict[str, Any]]) -> dict[str, int]:
    sets, frames = [], []
    for entry in score_sets:
        slug = entry["urn"].replace("urn:mavedb:", "")
        meta = json.loads((raw_dir / f"{slug}.json").read_text())
        sets.append(score_set_row(meta, entry))
        df = pl.read_csv(
            raw_dir / f"{slug}.scores.csv", infer_schema=False, null_values=["NA", ""]
        ).select("accession", "hgvs_nt", "hgvs_pro", "score")
        df = df.with_columns(
            pl.col("score").cast(pl.Float64),
            pl.lit(entry["urn"]).alias("score_set_urn"),
            match_keys(df, entry["gene"], entry["match_level"]).alias("match_key"),
        ).rename({"accession": "variant_urn"})
        frames.append(df)
    out = staging_dir / "mavedb" / "current"
    out.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(sets).with_columns(
        pl.col("published_date").str.to_date(strict=False),
        pl.col("num_variants").cast(pl.Int32),
    ).write_parquet(out / "score_sets.parquet")
    scores = pl.concat(frames)
    scores.write_parquet(out / "scores.parquet")
    log.info("staged mavedb", extra={"score_sets": len(sets), "rows": scores.height})
    return {"score_sets": len(sets), "scores": scores.height}
