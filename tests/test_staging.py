"""Parsing rules for the staging step."""

from __future__ import annotations

import polars as pl
import pytest

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
    df = pl.DataFrame({"n": ["NM_000546.6(TP53):c.524G>A (p.Arg175His)", "NM_000059.4(BRCA2):c.7436-10T>A"]})
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


def test_grch37_rows_and_par_duplicates_dropped(fixture_paths) -> None:  # type: ignore[no-untyped-def]
    staged = pl.read_parquet(fixture_paths.staging / "clinvar" / "2026-10" / "variants.parquet")
    assert staged.height == 8
    assert staged["variation_id"].is_unique().all()
