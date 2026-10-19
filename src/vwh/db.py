"""Thin engine layer so the same SQL runs on DuckDB and PostgreSQL."""

from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from vwh.config import REPO_ROOT
from vwh.logs import get_logger

log = get_logger(__name__)
MIGRATIONS_DIR = REPO_ROOT / "migrations"
_MIGRATION_RE = re.compile(r"^(\d{4})_[a-z0-9_]+(?:\.(duckdb|postgres))?\.sql$")

Rows = list[tuple[Any, ...]]


class Engine:
    name = "base"

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        raise NotImplementedError

    def query(self, sql: str, params: Sequence[Any] | None = None) -> tuple[list[str], Rows]:
        raise NotImplementedError

    def stage_parquet(self, table: str, path: Path) -> int:
        """Create a temporary table from a Parquet file and return its row count."""
        raise NotImplementedError

    def begin(self) -> None:
        self.execute("BEGIN")

    def commit(self) -> None:
        self.execute("COMMIT")

    def rollback(self) -> None:
        self.execute("ROLLBACK")

    def close(self) -> None:
        raise NotImplementedError

    def scalar(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        _, rows = self.query(sql, params)
        return rows[0][0] if rows else None


class DuckDBEngine(Engine):
    name = "duckdb"

    def __init__(self, path: str | Path = ":memory:", threads: int = 6) -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path))
        self.con.execute(f"SET threads = {int(threads)}")

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        self.con.execute(sql, list(params) if params is not None else None)

    def query(self, sql: str, params: Sequence[Any] | None = None) -> tuple[list[str], Rows]:
        cur = self.con.execute(sql, list(params) if params is not None else None)
        cols = [d[0] for d in cur.description] if cur.description else []
        return cols, cur.fetchall()

    def stage_parquet(self, table: str, path: Path) -> int:
        self.con.execute(f"DROP TABLE IF EXISTS {table}")
        self.con.execute(f"CREATE TEMP TABLE {table} AS SELECT * FROM read_parquet(?)", [str(path)])
        return int(self.scalar(f"SELECT count(*) FROM {table}"))

    def close(self) -> None:
        self.con.close()


_PG_TYPES = {
    "int8": "BIGINT",
    "int16": "SMALLINT",
    "int32": "INTEGER",
    "int64": "BIGINT",
    "double": "DOUBLE PRECISION",
    "float": "REAL",
    "bool": "BOOLEAN",
    "date32[day]": "DATE",
    "string": "TEXT",
    "large_string": "TEXT",
}


class PostgresEngine(Engine):
    name = "postgres"

    def __init__(self, dsn: str, schema: str | None = None) -> None:
        import psycopg

        self.con = psycopg.connect(dsn, autocommit=True)
        if schema:
            # Tests use one schema per fixture so they can share one server.
            self.con.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            self.con.execute(f'SET search_path TO "{schema}"')

    @staticmethod
    def _pg(sql: str) -> str:
        return sql.replace("?", "%s")

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> None:
        with self.con.cursor() as cur:
            if params is None:
                cur.execute(sql)
            else:
                cur.execute(self._pg(sql), list(params))

    def query(self, sql: str, params: Sequence[Any] | None = None) -> tuple[list[str], Rows]:
        with self.con.cursor() as cur:
            if params is None:
                cur.execute(sql)
            else:
                cur.execute(self._pg(sql), list(params))
            cols = [d.name for d in cur.description] if cur.description else []
            return cols, list(cur.fetchall()) if cur.description else []

    def stage_parquet(self, table: str, path: Path) -> int:
        tbl = pq.read_table(path)
        cols = ", ".join(f"{f.name} {_PG_TYPES.get(str(f.type), 'TEXT')}" for f in tbl.schema)
        self.execute(f"DROP TABLE IF EXISTS {table}")
        self.execute(f"CREATE TEMP TABLE {table} ({cols})")
        buf = io.BytesIO()
        pacsv.write_csv(tbl, buf, pacsv.WriteOptions(include_header=False))
        buf.seek(0)
        with (
            self.con.cursor() as cur,
            cur.copy(f"COPY {table} FROM STDIN WITH (FORMAT csv, NULL '')") as copy,
        ):
            while chunk := buf.read(1 << 20):
                copy.write(chunk)
        return int(self.scalar(f"SELECT count(*) FROM {table}"))

    def close(self) -> None:
        self.con.close()


def connect(
    dsn: str | None = None, duckdb_path: str | Path | None = None, schema: str | None = None
) -> Engine:
    if dsn:
        return PostgresEngine(dsn, schema=schema)
    return DuckDBEngine(duckdb_path or ":memory:")


def migration_files(engine_name: str) -> list[Path]:
    files = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        m = _MIGRATION_RE.match(path.name)
        if not m:
            raise ValueError(f"bad migration file name: {path.name}")
        if m.group(2) in (None, engine_name):
            files.append(path)
    return files


def migrate(engine: Engine) -> list[str]:
    """Apply pending migrations in order; refuse if an applied file was edited."""
    engine.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " filename TEXT PRIMARY KEY, sha256 TEXT NOT NULL,"
        " applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp)"
    )
    _, rows = engine.query("SELECT filename, sha256 FROM schema_migrations")
    applied: dict[str, str] = {str(f): str(h) for f, h in rows}
    done = []
    for path in migration_files(engine.name):
        text = path.read_text()
        digest = hashlib.sha256(text.encode()).hexdigest()
        if path.name in applied:
            if applied[path.name] != digest:
                raise RuntimeError(
                    f"{path.name} changed after it was applied; add a new migration instead"
                )
            continue
        engine.begin()
        try:
            engine.execute(text)
            engine.execute(
                "INSERT INTO schema_migrations (filename, sha256) VALUES (?, ?)",
                [path.name, digest],
            )
            engine.commit()
        except Exception:
            engine.rollback()
            raise
        log.info("migration applied", extra={"file": path.name, "engine": engine.name})
        done.append(path.name)
    return done
