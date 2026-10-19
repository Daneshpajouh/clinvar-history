"""Every cookbook query against the fixture warehouse, on each available engine."""

from __future__ import annotations

from typing import Any

import pytest

from clinvar_history import queries
from clinvar_history.config import Paths
from clinvar_history.db import Engine

from .conftest import load_all


def rows(engine: Engine, name: str) -> list[tuple[Any, ...]]:
    _, result = queries.run(engine, name)
    return [tuple(queries._plain(v) for v in r) for r in result]


def test_conflicting_by_gene(loaded_engine: Engine) -> None:
    # GENEX: V5 is conflicting, V10 is a copy number loss without VCF alleles;
    # V6 left ClinVar in 2026-10 and no longer counts.
    assert rows(loaded_engine, "01") == [("GENEX", 1, 2, 50.0, 1)]


def test_review_star_distribution(loaded_engine: Engine) -> None:
    assert rows(loaded_engine, "02") == [
        (3, 1, 11.11, 11.11),
        (2, 2, 22.22, 33.33),
        (1, 5, 55.56, 88.89),
        (0, 1, 11.11, 100.0),
    ]


def test_reclassified_between_releases(loaded_engine: Engine) -> None:
    # V1 moved VUS -> P/LP. V4 went Benign -> Likely benign: a new SCD version
    # but the same class, so it is not listed.
    assert rows(loaded_engine, "03") == [("VUS", "P/LP", 1)]


def test_rare_plp_by_ancestry(loaded_engine: Engine) -> None:
    assert rows(loaded_engine, "04") == [
        ("afr", 4, 1, 0, 1),
        ("all", 4, 2, 2, 0),
        ("nfe", 4, 2, 2, 0),
    ]


def test_plp_common_in_a_group(loaded_engine: Engine) -> None:
    assert rows(loaded_engine, "05") == [
        (
            "BRCA1",
            "17-43045712-G-A",
            "NM_007294.4(BRCA1):c.5096G>A (p.Arg1699Gln)",
            1,
            "afr",
            0.002,
            4,
            2000,
        ),
    ]


def test_mave_concordance(loaded_engine: Engine) -> None:
    # BRCA1 has no B/LB match with a star, so only TP53 is reported.
    # p.Arg175His is scored twice (-3.0, -2.0) and counts once at the mean,
    # -2.5. P/LP -2.5, -1.0 against B/LB 0.8, 1.0: every P/LP score is lower,
    # AUC 1; median P/LP (-2.5 + -1.0) / 2.
    assert rows(loaded_engine, "06") == [
        ("TP53", "urn:mavedb:00000068-0-1", "protein", 2, 2, -1.75, 0.9, 1.0),
    ]


def test_top_submitters_by_gene(loaded_engine: Engine) -> None:
    assert rows(loaded_engine, "07") == [
        ("BRCA1", 1, "LabA", 2),
        ("BRCA1", 2, "ExpertPanel", 1),
        ("BRCA1", 2, "LabB", 1),
        ("BRCA1", 2, "LabD", 1),
        ("TP53", 1, "LabB", 3),
        ("TP53", 2, "LabA", 2),
        ("TP53", 3, "LabC", 1),
    ]


def test_graphkb_style_snvs(loaded_engine: Engine) -> None:
    got = [(r[0], r[2]) for r in rows(loaded_engine, "08")]
    assert got == [
        ("BRCA1", "chr17:g.43045712G>A"),
        ("BRCA1", "chr17:g.43045713C>T"),
        ("TP53", "chr17:g.7675088C>T"),
        ("TP53", "chr17:g.7675089G>A"),
    ]


def test_resolve_rejects_ambiguous_name() -> None:
    with pytest.raises(FileNotFoundError):
        queries.resolve("0")


def test_frequency_queries_read_only_the_latest_gnomad_release(
    empty_engine: Engine, fixture_paths: Paths
) -> None:
    load_all(empty_engine, fixture_paths)
    # An older release in which V1 looked common in afr must not change the answer.
    empty_engine.execute(
        "INSERT INTO source_release (source, label, status) VALUES ('gnomad', '4.0', 'loaded')"
    )
    old = empty_engine.scalar("SELECT release_id FROM source_release WHERE label = '4.0'")
    empty_engine.execute(
        "INSERT INTO population_frequency (variant_key, release_id, ancestry_group, ac, an, af,"
        " nhomalt, filter) VALUES ('17-43045712-G-A', ?, 'afr', 1000, 2000, 0.5, 0, 'PASS')",
        [old],
    )
    assert [r[4:6] for r in rows(empty_engine, "05")] == [("afr", 0.002)]
    assert rows(empty_engine, "04")[0] == ("afr", 4, 1, 0, 1)
