"""Release loads: idempotence, ordering, and recovery from an interrupted refresh."""

from __future__ import annotations

from typing import Any

import pytest

from vwh import load
from vwh.config import Paths
from vwh.db import Engine, migrate
from vwh.validate import run_checks

TABLES = [
    "source_release", "provenance", "gene", "clinvar_variation", "classification",
    "submitter", "submission",
]  # fmt: skip


def snapshot(engine: Engine) -> dict[str, Any]:
    out: dict[str, Any] = {t: engine.scalar(f"SELECT count(*) FROM {t}") for t in TABLES}
    _, rows = engine.query(
        "SELECT variation_id, clinical_significance, is_current, valid_to_release_id"
        " FROM classification ORDER BY variation_id, valid_from_release_id"
    )
    out["classification_rows"] = rows
    return out


def test_counts_after_two_releases(loaded_engine: Engine) -> None:
    assert loaded_engine.scalar("SELECT count(*) FROM clinvar_variation") == 9
    # 7 versions from 2025-10, then V1 and V4 changed and V8, V9 arrived.
    assert loaded_engine.scalar("SELECT count(*) FROM classification") == 11
    assert loaded_engine.scalar("SELECT count(*) FROM classification WHERE is_current") == 8
    # 15 rows: one repeated SCV dropped at staging, one orphan VariationID dropped at load.
    assert loaded_engine.scalar(
        "SELECT count(*) FROM submission AS s INNER JOIN v_clinvar_release AS r"
        " ON s.release_id = r.release_id AND r.recency_rank = 1"
    ) == 13


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


@pytest.mark.parametrize("step", ["release", "clinvar_variation", "classification_close",
                                  "classification_open", "submission"])
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
    # The retry starts from a clean state and completes.
    assert load.load_clinvar(empty_engine, fixture_paths, "2026-10") is True
    assert empty_engine.scalar("SELECT count(*) FROM classification WHERE is_current") == 8


def test_unload_restores_previous_release(empty_engine: Engine, fixture_paths: Paths) -> None:
    migrate(empty_engine)
    load.load_clinvar(empty_engine, fixture_paths, "2025-10")
    before = snapshot(empty_engine)
    load.load_clinvar(empty_engine, fixture_paths, "2026-10")
    assert load.unload_latest_clinvar(empty_engine) == "2026-10"
    after = snapshot(empty_engine)
    # Sequences are not rewound and variant keys stay, so compare release content.
    # Submitters first seen in 2026-10 also stay; they are names, not assertions.
    for key in ("submitter", "source_release"):
        after.pop(key)
        before.pop(key)
    assert after == before
    assert empty_engine.scalar(
        "SELECT status FROM source_release WHERE label = '2026-10'"
    ) == "rolled_back"
    # Loading the same release again reuses the audit row and succeeds.
    assert load.load_clinvar(empty_engine, fixture_paths, "2026-10") is True


def test_changed_file_is_refused(empty_engine: Engine, fixture_paths: Paths) -> None:
    migrate(empty_engine)
    load.load_clinvar(empty_engine, fixture_paths, "2025-10")
    empty_engine.execute("UPDATE provenance SET sha256 = repeat('0', 64)")
    with pytest.raises(load.LoadError, match="different files"):
        load.load_clinvar(empty_engine, fixture_paths, "2025-10")
