"""Migration runner behaviour."""

from __future__ import annotations

from pathlib import Path

import pytest

from clinvar_history.db import Engine, migrate, migration_files


def test_engine_specific_files_are_filtered() -> None:
    duck = [p.name for p in migration_files("duckdb")]
    pg = [p.name for p in migration_files("postgres")]
    assert not any(".postgres." in n for n in duck)
    assert "0005_roles.postgres.sql" in pg


def test_migrate_twice_applies_nothing_new(empty_engine: Engine) -> None:
    first = migrate(empty_engine)
    assert first
    assert migrate(empty_engine) == []


def test_edited_migration_is_detected(empty_engine: Engine) -> None:
    migrate(empty_engine)
    empty_engine.execute("UPDATE schema_migrations SET sha256 = 'x' WHERE filename LIKE '0001%'")
    with pytest.raises(RuntimeError, match="changed after it was applied"):
        migrate(empty_engine)


def test_literal_percent_and_parameters_together(empty_engine: Engine) -> None:
    # On PostgreSQL the ? placeholders become %s, so the % in LIKE must survive.
    migrate(empty_engine)
    got = empty_engine.scalar(
        "SELECT count(*) FROM review_status WHERE review_status LIKE 'criteria%' AND stars >= ?",
        [1],
    )
    assert got == 3


def test_empty_string_and_null_survive_staging(empty_engine: Engine, tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = tmp_path / "t.parquet"
    pq.write_table(pa.table({"s": ["", None, "x"], "n": [1, None, 3]}), path)
    assert empty_engine.stage_parquet("stg_t", path) == 3
    _, got = empty_engine.query("SELECT s, n FROM stg_t ORDER BY n NULLS LAST, s")
    assert got == [("", 1), ("x", 3), (None, None)]
