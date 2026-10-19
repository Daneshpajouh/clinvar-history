"""Benchmark harness: storage layouts on DuckDB, and DuckDB vs SQLite vs PostgreSQL.

The input is one flat table of current ClinVar records exported from the
loaded DuckDB warehouse, so every engine answers the same questions on the
same rows. Each case runs once to warm caches, then `repeats` timed runs.
"""

from __future__ import annotations

import csv
import functools
import io
import os
import platform
import sqlite3
import statistics
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from clinvar_history.config import Paths
from clinvar_history.logs import get_logger

log = get_logger(__name__)

EXPORT_SQL = """
SELECT variation_id, variant_key, chrom, pos, ref, alt, gene_symbol, clinsig_class, stars
FROM v_variant_current
WHERE variant_key IS NOT NULL
"""

# BRCA1 on GRCh38 (Ensembl ENSG00000012048).
REGION = ("17", 43044292, 43170245)

QUERIES = {
    "point_lookup": (
        "SELECT variation_id, clinsig_class, stars FROM {t} WHERE variant_key = '{key}'"
    ),
    "region_count": (
        "SELECT clinsig_class, count(*) FROM {t} WHERE chrom = '17'"
        " AND pos BETWEEN 43044292 AND 43170245 GROUP BY clinsig_class ORDER BY clinsig_class"
    ),
    "gene_plp_top10": (
        "SELECT gene_symbol, count(*) AS n FROM {t} WHERE clinsig_class = 'P/LP'"
        " AND gene_symbol IS NOT NULL GROUP BY gene_symbol ORDER BY n DESC, gene_symbol LIMIT 10"
    ),
}

Row = dict[str, Any]


def machine_info() -> dict[str, Any]:
    def sysctl(key: str) -> str:
        try:
            return subprocess.run(
                ["sysctl", "-n", key], capture_output=True, text=True, check=True
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unknown"

    return {
        "cpu": sysctl("machdep.cpu.brand_string"),
        "logical_cpus": os.cpu_count(),
        "memory_gb": round(int(sysctl("hw.memsize") or 0) / 2**30, 1)
        if sysctl("hw.memsize").isdigit()
        else "unknown",
        "os": platform.platform(),
        "python": platform.python_version(),
        "duckdb": duckdb.__version__,
        "sqlite": sqlite3.sqlite_version,
    }


def _fetch(con: Any, sql: str) -> list[Any]:
    return list(con.execute(sql).fetchall())


def _time(fn: Callable[[], Any], repeats: int) -> tuple[float, float, Any]:
    result = fn()  # warm-up run, also the result we report
    times = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t)
    return min(times), statistics.median(times), result


def export_inputs(paths: Paths, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(paths.duckdb_path), read_only=True)
    files = {
        "parquet_unsorted": out_dir / "current_unsorted.parquet",
        "parquet_sorted": out_dir / "current_sorted.parquet",
        "csv_gz": out_dir / "current.csv.gz",
    }
    # Unsorted means VariationID order, which is unrelated to genomic position.
    con.execute(
        f"COPY ({EXPORT_SQL} ORDER BY variation_id) TO '{files['parquet_unsorted']}'"
        " (FORMAT parquet, ROW_GROUP_SIZE 122880)"
    )
    con.execute(
        f"COPY ({EXPORT_SQL} ORDER BY chrom, pos) TO '{files['parquet_sorted']}'"
        " (FORMAT parquet, ROW_GROUP_SIZE 122880)"
    )
    con.execute(f"COPY ({EXPORT_SQL} ORDER BY variation_id) TO '{files['csv_gz']}' (HEADER)")
    con.close()
    return files


def _row(
    engine: str,
    layout: str,
    query: str,
    tmin: float,
    tmed: float,
    rows: int,
    n_input: int,
    repeats: int,
) -> Row:
    return {
        "engine": engine,
        "layout": layout,
        "query": query,
        "min_ms": round(tmin * 1000, 2),
        "median_ms": round(tmed * 1000, 2),
        "result_rows": rows,
        "input_rows": n_input,
        "repeats": repeats,
    }


def bench_duckdb_files(files: dict[str, Path], key: str, n: int, repeats: int) -> list[Row]:
    con = duckdb.connect()
    con.execute("SET threads = 6")
    out = []
    readers = {
        "csv_gz": f"read_csv('{files['csv_gz']}', header=true, types={{'chrom': 'VARCHAR'}})",
        "parquet_unsorted": f"read_parquet('{files['parquet_unsorted']}')",
        "parquet_sorted": f"read_parquet('{files['parquet_sorted']}')",
    }
    for layout, src in readers.items():
        for qname, q in QUERIES.items():
            sql = q.format(t=src, key=key)
            tmin, tmed, res = _time(functools.partial(_fetch, con, sql), repeats)
            out.append(_row("duckdb", layout, qname, tmin, tmed, len(res), n, repeats))
    con.close()
    return out


def explain_duckdb(data_dir: Path, files: dict[str, Path], plans: Path) -> None:
    """Save EXPLAIN ANALYZE output with file paths relative to the data directory.

    Plans are committed to the repository, so they must not carry the path of
    the machine that produced them.
    """
    con = duckdb.connect()
    con.execute("SET threads = 6")
    con.execute(f"SET file_search_path = '{data_dir}'")
    for layout in ("parquet_unsorted", "parquet_sorted"):
        rel = files[layout].relative_to(data_dir)
        sql = QUERIES["region_count"].format(t=f"read_parquet('{rel}')", key="")
        rows = con.execute(f"EXPLAIN ANALYZE {sql}").fetchall()
        text = normalise_paths(rows[0][1], data_dir)
        (plans / f"duckdb_region_count_{layout}.txt").write_text(text + "\n")
    con.close()


def normalise_paths(text: str, data_dir: Path) -> str:
    return text.replace(str(data_dir.resolve()), "$DATA_DIR").replace(str(data_dir), "$DATA_DIR")


def bench_sqlite(files: dict[str, Path], key: str, n: int, repeats: int, work: Path) -> list[Row]:
    db = work / "bench.sqlite"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    tbl = pq.read_table(files["parquet_unsorted"])
    con.execute(
        "CREATE TABLE cur (variation_id INTEGER, variant_key TEXT, chrom TEXT, pos INTEGER,"
        " ref TEXT, alt TEXT, gene_symbol TEXT, clinsig_class TEXT, stars INTEGER)"
    )
    con.executemany(
        "INSERT INTO cur VALUES (?,?,?,?,?,?,?,?,?)",
        zip(*[c.to_pylist() for c in tbl.columns], strict=True),
    )
    con.commit()
    out = []
    for layout, ddl in (
        ("no_index", None),
        (
            "btree_index",
            "CREATE INDEX cur_key ON cur (variant_key);"
            " CREATE INDEX cur_pos ON cur (chrom, pos); ANALYZE;",
        ),
    ):
        if ddl:
            con.executescript(ddl)
        for qname, q in QUERIES.items():
            sql = q.format(t="cur", key=key)
            tmin, tmed, res = _time(functools.partial(_fetch, con, sql), repeats)
            out.append(_row("sqlite", layout, qname, tmin, tmed, len(res), n, repeats))
    con.close()
    return out


def bench_postgres(
    dsn: str, files: dict[str, Path], key: str, n: int, repeats: int, plans: Path
) -> list[Row]:
    import psycopg

    con = psycopg.connect(dsn, autocommit=True)
    con.execute("DROP TABLE IF EXISTS bench_cur")
    con.execute(
        "CREATE TABLE bench_cur (variation_id BIGINT, variant_key TEXT, chrom TEXT, pos INTEGER,"
        " ref TEXT, alt TEXT, gene_symbol TEXT, clinsig_class TEXT, stars INTEGER)"
    )
    buf = io.BytesIO()
    pacsv.write_csv(
        pq.read_table(files["parquet_unsorted"]), buf, pacsv.WriteOptions(include_header=False)
    )
    buf.seek(0)
    with con.cursor() as cur, cur.copy("COPY bench_cur FROM STDIN WITH (FORMAT csv)") as copy:
        while chunk := buf.read(1 << 20):
            copy.write(chunk)
    con.execute("VACUUM ANALYZE bench_cur")
    out = []
    for layout, ddl in (
        ("no_index", None),
        (
            "hash_key_btree_pos",
            "CREATE INDEX bench_cur_key ON bench_cur USING hash (variant_key);"
            " CREATE INDEX bench_cur_pos ON bench_cur (chrom, pos); ANALYZE bench_cur",
        ),
    ):
        if ddl:
            con.execute(ddl)
        for qname, q in QUERIES.items():
            sql = q.format(t="bench_cur", key=key)
            tmin, tmed, res = _time(functools.partial(_fetch, con, sql), repeats)
            out.append(_row("postgres", layout, qname, tmin, tmed, len(res), n, repeats))
            if qname in ("region_count", "point_lookup"):
                plan = con.execute(f"EXPLAIN (ANALYZE, BUFFERS) {sql}").fetchall()
                (plans / f"postgres_{qname}_{layout}.txt").write_text(
                    "\n".join(r[0] for r in plan) + "\n"
                )
    version = con.execute("SHOW server_version").fetchone()
    log.info("postgres version", extra={"server_version": version[0] if version else None})
    con.execute("DROP TABLE bench_cur")
    con.close()
    return out


def run_all(paths: Paths, dsn: str | None, repeats: int, plans: Path) -> list[Row]:
    work = paths.data_dir / "bench"
    plans.mkdir(parents=True, exist_ok=True)
    files = export_inputs(paths, work)
    con = duckdb.connect()
    n = int(_fetch(con, f"SELECT count(*) FROM read_parquet('{files['parquet_sorted']}')")[0][0])
    # A real P/LP BRCA1 key, so the lookup returns one row.
    key = str(
        _fetch(
            con,
            f"SELECT variant_key FROM read_parquet('{files['parquet_sorted']}')"
            " WHERE gene_symbol = 'BRCA1' AND clinsig_class = 'P/LP' ORDER BY pos LIMIT 1",
        )[0][0]
    )
    con.close()
    sizes = {k: v.stat().st_size for k, v in files.items()}
    log.info("bench inputs", extra={"rows": n, "lookup_key": key, **sizes})
    rows = bench_duckdb_files(files, key, n, repeats)
    explain_duckdb(paths.data_dir, files, plans)
    rows += bench_sqlite(files, key, n, repeats, work)
    if dsn:
        rows += bench_postgres(dsn, files, key, n, repeats, plans)
    for r in rows:
        r["input_bytes"] = sizes.get(r["layout"], "")
    return rows


def write_csv(rows: list[Row], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
