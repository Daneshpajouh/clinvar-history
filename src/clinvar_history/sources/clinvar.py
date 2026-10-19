"""Parse ClinVar tab-delimited release files into typed Parquet staging tables."""

from __future__ import annotations

import gzip
from pathlib import Path

import polars as pl

from clinvar_history.logs import get_logger

log = get_logger(__name__)

# Name looks like "NM_000546.6(TP53):c.524G>A (p.Arg175His)".
NAME_RE = r"^(?<tx>N[MR]_\d+\.\d+)\((?<gene>[^)]+)\):(?<c>c\.[^ ]+)(?: \((?<p>p\.[^)]+)\))?$"
PROTEIN_SUB_RE = r"^p\.[A-Z][a-z]{2}\d+(?:[A-Z][a-z]{2}|=)$"

CLASS_EXACT = {
    "pathogenic": "P/LP",
    "likely pathogenic": "P/LP",
    "pathogenic/likely pathogenic": "P/LP",
    "benign": "B/LB",
    "likely benign": "B/LB",
    "benign/likely benign": "B/LB",
    "uncertain significance": "VUS",
    "conflicting classifications of pathogenicity": "Conflicting",
    "conflicting interpretations of pathogenicity": "Conflicting",
}


def clinsig_class(col: str) -> pl.Expr:
    """Collapse ClinVar's free-form germline classification into five classes.

    Only the exact strings in CLASS_EXACT map to P/LP, B/LB, VUS or Conflicting;
    compound values such as "Pathogenic; risk factor" fall into Other so the
    counts stay conservative.
    """
    return (
        pl.col(col)
        .str.to_lowercase()
        .replace_strict(CLASS_EXACT, default="Other", return_dtype=pl.String)
    )


def _parse_date(col: str) -> pl.Expr:
    return pl.col(col).str.strptime(pl.Date, "%b %d, %Y", strict=False)


def variant_class(ref: pl.Expr, alt: pl.Expr) -> pl.Expr:
    """VCF-style class: an insertion or deletion keeps the shared anchor base."""
    rl, al = ref.str.len_chars(), alt.str.len_chars()
    return (
        pl.when((rl == 1) & (al == 1))
        .then(pl.lit("snv"))
        .when(rl == al)
        .then(pl.lit("mnv"))
        .when((rl == 1) & alt.str.starts_with(ref))
        .then(pl.lit("insertion"))
        .when((al == 1) & ref.str.starts_with(alt))
        .then(pl.lit("deletion"))
        .otherwise(pl.lit("delins"))
    )


def read_variant_summary(path: Path) -> pl.DataFrame:
    df = pl.read_csv(
        path, separator="\t", quote_char=None, infer_schema=False, null_values=["-", "na"]
    )
    return df.rename({"#AlleleID": "AlleleID"})


def stage_variants(path: Path, assembly: str = "GRCh38") -> pl.DataFrame:
    raw = read_variant_summary(path)
    df = raw.filter(pl.col("Assembly") == assembly)
    # Pseudoautosomal variants appear once on chrX and once on chrY with the
    # same VariationID; keep the chrX row so the key is unique.
    df = df.sort(["VariationID", "Chromosome"]).unique(
        subset=["VariationID"], keep="first", maintain_order=True
    )
    name = pl.col("Name").str.extract_groups(NAME_RE)
    has_vcf = (
        pl.col("PositionVCF").is_not_null()
        & (pl.col("PositionVCF") != "-1")
        & pl.col("ReferenceAlleleVCF").str.contains(r"^[ACGTN]+$")
        & pl.col("AlternateAlleleVCF").str.contains(r"^[ACGTN]+$")
    )
    out = df.select(
        pl.col("VariationID").cast(pl.Int64).alias("variation_id"),
        pl.col("AlleleID").cast(pl.Int64).alias("allele_id"),
        pl.when(has_vcf)
        .then(
            pl.concat_str(
                [
                    pl.col("Chromosome"),
                    pl.col("PositionVCF"),
                    pl.col("ReferenceAlleleVCF"),
                    pl.col("AlternateAlleleVCF"),
                ],
                separator="-",
            )
        )
        .alias("variant_key"),
        pl.when(has_vcf).then(pl.col("Chromosome")).alias("chrom"),
        pl.when(has_vcf).then(pl.col("PositionVCF").cast(pl.Int32)).alias("pos"),
        pl.when(has_vcf).then(pl.col("ReferenceAlleleVCF")).alias("ref"),
        pl.when(has_vcf).then(pl.col("AlternateAlleleVCF")).alias("alt"),
        pl.col("GeneID").cast(pl.Int32).alias("gene_id"),
        pl.col("GeneSymbol").alias("gene_symbol"),
        pl.col("HGNC_ID").alias("hgnc_id"),
        pl.col("Name").alias("name"),
        pl.col("Type").alias("variant_type"),
        name.struct.field("tx").alias("transcript"),
        name.struct.field("c").alias("hgvs_c"),
        name.struct.field("p").alias("protein_change"),
        name.struct.field("gene").alias("name_gene"),
        pl.col("ClinicalSignificance").fill_null("-").alias("clinical_significance"),
        pl.col("ReviewStatus").fill_null("-").alias("review_status"),
        pl.col("NumberSubmitters").cast(pl.Int32).alias("number_submitters"),
        _parse_date("LastEvaluated").alias("last_evaluated"),
    )
    out = out.with_columns(
        clinsig_class(col="clinical_significance").alias("clinsig_class"),
        pl.when(pl.col("variant_key").is_not_null())
        .then(variant_class(pl.col("ref"), pl.col("alt")))
        .alias("variant_class"),
        pl.when(pl.col("hgvs_c").is_not_null())
        .then(
            pl.concat_str(
                [pl.col("transcript").str.replace(r"\.\d+$", ""), pl.col("hgvs_c")], separator=":"
            )
        )
        .alias("hgvs_c_key"),
        pl.when(pl.col("protein_change").str.contains(PROTEIN_SUB_RE))
        .then(pl.concat_str([pl.col("name_gene"), pl.col("protein_change")], separator=":"))
        .alias("hgvs_p_key"),
        # gene_id -1 marks a variant spanning several genes
        pl.when(pl.col("gene_id") > 0).then(pl.col("gene_id")).alias("gene_id"),
    ).drop("name_gene")
    log.info("staged clinvar variants", extra={"file": path.name, "rows": out.height})
    return out


def read_submission_summary(path: Path) -> pl.DataFrame:
    # The file opens with "##" comment lines followed by a "#VariationID" header.
    with gzip.open(path, "rt") as fh:
        skip = 0
        for line in fh:
            if line.startswith("#VariationID\t"):
                break
            skip += 1
    df = pl.read_csv(
        path,
        separator="\t",
        quote_char=None,
        infer_schema=False,
        skip_rows=skip,
        null_values=["-", "na"],
    )
    return df.rename({"#VariationID": "VariationID"})


def stage_submissions(path: Path) -> pl.DataFrame:
    df = read_submission_summary(path)
    scv = pl.col("SCV").str.extract_groups(r"^(?<acc>SCV\d+)\.(?<ver>\d+)$")
    out = df.select(
        pl.col("VariationID").cast(pl.Int64).alias("variation_id"),
        scv.struct.field("acc").alias("scv"),
        scv.struct.field("ver").cast(pl.Int32).alias("scv_version"),
        pl.col("Submitter").alias("submitter"),
        pl.col("ClinicalSignificance").alias("clinical_significance"),
        _parse_date("DateLastEvaluated").alias("date_last_evaluated"),
        pl.col("ReviewStatus").alias("review_status"),
        pl.col("CollectionMethod").alias("collection_method"),
        pl.col("SubmittedGeneSymbol").alias("submitted_gene_symbol"),
    ).with_columns(
        clinsig_class(col="clinical_significance").fill_null("Other").alias("clinsig_class")
    )
    bad = out.filter(pl.col("scv").is_null() | pl.col("submitter").is_null()).height
    if bad:
        raise ValueError(f"{path.name}: {bad} rows without a parseable SCV or submitter")
    # A handful of SCVs are listed twice with different classifications (2026-10:
    # SCV000058352 from OMIM as both 'not provided' and 'Pathogenic'). Keep the
    # first row in file order so (release, scv) stays a key, and log the count.
    deduped = out.unique(subset=["scv"], keep="first", maintain_order=True)
    log.info(
        "staged clinvar submissions",
        extra={
            "file": path.name,
            "rows": deduped.height,
            "repeated_scv_rows_dropped": out.height - deduped.height,
        },
    )
    return deduped


def stage_release(raw_dir: Path, staging_dir: Path, release: str) -> dict[str, int]:
    out_dir = staging_dir / "clinvar" / release
    out_dir.mkdir(parents=True, exist_ok=True)
    variants = stage_variants(raw_dir / f"variant_summary_{release}.txt.gz")
    variants.write_parquet(out_dir / "variants.parquet")
    subs = stage_submissions(raw_dir / f"submission_summary_{release}.txt.gz")
    subs.write_parquet(out_dir / "submissions.parquet")
    return {"variants": variants.height, "submissions": subs.height}
