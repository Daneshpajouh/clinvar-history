"""Migration runner behaviour."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from clinvar_history import db
from clinvar_history.db import Engine, migrate, migration_files


def test_engine_specific_files_are_filtered() -> None:
    duck = [p.name for p in migration_files("duckdb")]
    pg = [p.name for p in migration_files("postgres")]
    assert not any(".postgres." in n for n in duck)
    assert "0005_roles.postgres.sql" in pg


def test_loader_role_can_write_every_table(empty_engine: Engine) -> None:
    # 0005 granted only the tables that existed then; 0006 added one after it
    if empty_engine.name != "postgres":
        pytest.skip("the roles exist only on PostgreSQL")
    migrate(empty_engine)
    _, rows = empty_engine.query(
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
        # schema-qualified: PostgreSQL may test the privilege before it applies the schema filter
        " AND NOT has_table_privilege("
        "'clinvar_history_loader', format('%I.%I', table_schema, table_name), 'INSERT')"
    )
    assert [r[0] for r in rows] == []


def test_missing_migrations_folder_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="the package is incomplete"):
        migration_files("duckdb")


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


def test_0008_keys_existing_rows_by_digest(
    empty_engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Upgrade a warehouse that 0001 to 0007 built and that already holds rows.
    for path in sorted(db.MIGRATIONS_DIR.glob("*.sql")):
        if path.name < "0008":
            (tmp_path / path.name).write_text(path.read_text())
    monkeypatch.setattr(db, "MIGRATIONS_DIR", tmp_path)
    migrate(empty_engine)
    key = "17-43045712-G-A"
    for sql in (
        "INSERT INTO source_release (label, source, status) VALUES ('4.1', 'gnomad', 'loaded')",
        f"INSERT INTO variant VALUES ('{key}', '17', 43045712, 'G', 'A', 'snv')",
        "INSERT INTO clinvar_variation (variation_id, allele_id, variant_key, variant_type,"
        f" first_release_id) VALUES (55, 66, '{key}', 'single nucleotide variant', 1)",
        "INSERT INTO clinvar_variation (variation_id, allele_id, variant_type, first_release_id)"
        " VALUES (56, 67, 'Deletion', 1)",
        "INSERT INTO population_frequency (variant_key, release_id, ancestry_group, ac, an,"
        f" filter) VALUES ('{key}', 1, 'all', 1, 10, 'PASS')",
    ):
        empty_engine.execute(sql)
    monkeypatch.undo()
    assert [p.startswith("0008_") for p in migrate(empty_engine)] == [True]
    digest = hashlib.md5(key.encode()).hexdigest()
    for table, want in (
        ("variant", [(digest,)]),
        ("clinvar_variation", [(digest,), (None,)]),
        ("population_frequency", [(digest,)]),
    ):
        got = empty_engine.query(f"SELECT variant_key_md5 FROM {table} ORDER BY 1 NULLS LAST")[1]
        assert got == want, table
    # the digest must match its key, and a child must name a known variant
    for bad in (
        "INSERT INTO variant VALUES ('1-1-A-C', '1', 1, 'A', 'C', 'snv', 'x')",
        "INSERT INTO population_frequency VALUES"
        " ('1-1-A-C', 1, 'all', 1, 10, NULL, NULL, 'PASS', md5('1-1-A-C'))",
    ):
        with pytest.raises(Exception, match=r"(?i)constraint|violat"):
            empty_engine.execute(bad)
