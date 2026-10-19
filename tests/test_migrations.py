"""Migration runner behaviour."""

from __future__ import annotations

import pytest

from vwh.db import Engine, migrate, migration_files


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
