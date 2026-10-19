"""Parsing rules for the staging step."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from vwh.config import Paths
from vwh.sources import clinvar, mavedb


@pytest.mark.parametrize(
    ("significance", "expected"),
    [
        ("Pathogenic", "P/LP"),
        ("Likely pathogenic", "P/LP"),
        ("Pathogenic/Likely pathogenic", "P/LP"),
        ("Benign/Likely benign", "B/LB"),
        ("Uncertain significance", "VUS"),
        ("Conflicting classifications of pathogenicity", "Conflicting"),
        ("Conflicting interpretations of pathogenicity", "Conflicting"),
        ("Pathogenic; risk factor", "Other"),
        ("not provided", "Other"),
    ],
)
def test_clinsig_class(significance: str, expected: str) -> None:
    df = pl.DataFrame({"s": [significance]}).select(clinvar.clinsig_class("s").alias("c"))
    assert df["c"][0] == expected


def test_name_parsing() -> None:
    df = pl.DataFrame(
        {"n": ["NM_000546.6(TP53):c.524G>A (p.Arg175His)", "NM_000059.4(BRCA2):c.7436-10T>A"]}
    )
    parts = df.select(pl.col("n").str.extract_groups(clinvar.NAME_RE).alias("g")).unnest("g")
    assert parts.row(0) == ("NM_000546.6", "TP53", "c.524G>A", "p.Arg175His")
    assert parts.row(1) == ("NM_000059.4", "BRCA2", "c.7436-10T>A", None)


def test_variant_class() -> None:
    df = pl.DataFrame({"r": ["G", "GA", "G", "AT", "GAT"], "a": ["A", "TC", "GTT", "A", "C"]})
    got = df.select(clinvar.variant_class(pl.col("r"), pl.col("a")).alias("c"))["c"].to_list()
    assert got == ["snv", "mnv", "insertion", "deletion", "delins"]


def test_mave_keys() -> None:
    df = pl.DataFrame(
        {"hgvs_nt": ["NM_007294.3:c.5565A>T", None], "hgvs_pro": [None, "p.[Arg175His;Pro72Arg]"]}
    )
    nt = df.select(mavedb.match_keys(df, "BRCA1", "nucleotide").alias("k"))["k"].to_list()
    assert nt == ["NM_007294:c.5565A>T", None]
    pro = df.select(mavedb.match_keys(df, "TP53", "protein").alias("k"))["k"].to_list()
    assert pro == [None, None]  # multi-variant protein changes get no key


def test_grch37_rows_dropped(fixture_paths: Paths) -> None:
    staged = pl.read_parquet(fixture_paths.staging / "clinvar" / "2026-10" / "variants.parquet")
    assert staged.height == 9  # 18 GRCh37 and GRCh38 rows plus V10, GRCh38 only
    assert staged["variation_id"].is_unique().all()


def test_variant_without_vcf_alleles_keeps_no_key(fixture_paths: Paths) -> None:
    staged = pl.read_parquet(fixture_paths.staging / "clinvar" / "2026-10" / "variants.parquet")
    v10 = staged.filter(pl.col("variation_id") == 1010).row(0, named=True)
    assert v10["variant_key"] is None
    assert v10["clinsig_class"] == "P/LP"
    assert v10["last_evaluated"] is None  # "sometime in 2024" does not parse


def test_par_duplicate_keeps_chrx(tmp_path: Path) -> None:
    import gzip

    header = (
        (Path(__file__).parent / "data" / "variant_summary_2026-10.tsv").read_text().splitlines()[0]
    )
    cols = header.split("\t")
    rows = []
    for chrom in ("Y", "X"):
        row = dict.fromkeys(cols, "-")
        row.update(
            {
                "#AlleleID": "1",
                "Type": "single nucleotide variant",
                "Name": "x",
                "ClinicalSignificance": "Benign",
                "Assembly": "GRCh38",
                "Chromosome": chrom,
                "ReviewStatus": "criteria provided, single submitter",
                "VariationID": "7",
                "PositionVCF": "100",
                "ReferenceAlleleVCF": "A",
                "AlternateAlleleVCF": "G",
            }
        )
        rows.append("\t".join(row[c] for c in cols))
    path = tmp_path / "vs.txt.gz"
    with gzip.open(path, "wt") as fh:
        fh.write("\n".join([header, *rows]) + "\n")
    staged = clinvar.stage_variants(path)
    assert staged["variant_key"].to_list() == ["X-100-A-G"]


def test_repeated_scv_keeps_first_row(fixture_paths: Paths) -> None:
    subs = pl.read_parquet(fixture_paths.staging / "clinvar" / "2026-10" / "submissions.parquet")
    rows = subs.filter(pl.col("scv") == "SCV0000011")
    assert rows.height == 1
    assert rows["clinical_significance"][0] == "Benign"
    assert rows["scv_version"][0] == 1


def test_mave_row_without_hgvs_has_no_key(fixture_paths: Paths) -> None:
    scores = pl.read_parquet(fixture_paths.staging / "mavedb" / "current" / "scores.parquet")
    row = scores.filter(pl.col("variant_urn") == "urn:mavedb:00000068-0-1#6").row(0, named=True)
    assert row["match_key"] is None
    assert row["score"] == 0.3
