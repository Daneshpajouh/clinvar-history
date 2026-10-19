"""A one-repeat benchmark on the fixture warehouse, and the data dictionary."""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest

from clinvar_history import bench
from clinvar_history.config import Paths
from clinvar_history.db import connect
from clinvar_history.dictionary import TABLES, render

from .conftest import build_raw, load_all, stage_all


@pytest.fixture(scope="module")
def file_warehouse(tmp_path_factory: pytest.TempPathFactory) -> Paths:
    paths = Paths(tmp_path_factory.mktemp("clinvar_history-bench"))
    build_raw(paths)
    stage_all(paths)
    engine = connect(duckdb_path=paths.duckdb_path)
    load_all(engine, paths)
    engine.close()
    return paths


def test_engines_agree_and_plans_carry_no_local_paths(
    file_warehouse: Paths, tmp_path: Path
) -> None:
    plans = tmp_path / "plans"
    dsn = os.environ.get("CLINVAR_HISTORY_PG_DSN")
    rows = bench.run_all(file_warehouse, dsn=dsn, repeats=1, plans=plans)
    engines = {"duckdb", "sqlite"} | ({"postgres"} if dsn else set())
    assert {r["engine"] for r in rows} == engines
    # 3 DuckDB layouts and 2 index layouts per row store, 3 queries each
    assert len(rows) == 9 + 6 * (len(engines) - 1)
    # Every engine and layout returns the same number of result rows per query:
    # 1 for the BRCA1 lookup, 2 classes in the BRCA1 region, and 2 genes with
    # P/LP (GENEX's P/LP record V10 has no GRCh38 key, so it is not exported).
    for query, expected in {"point_lookup": 1, "region_count": 2, "gene_plp_top10": 2}.items():
        assert {r["result_rows"] for r in rows if r["query"] == query} == {expected}
    for plan in plans.glob("duckdb_*.txt"):
        text = plan.read_text()
        assert str(file_warehouse.data_dir) not in text
        assert "bench/current_" in text

    out = tmp_path / "bench.csv"
    bench.write_csv(rows, out)
    assert out.read_text().splitlines()[0].startswith("engine,layout,query,min_ms")


def test_normalise_paths() -> None:
    text = "read_parquet('/srv/clinvar_history/bench/a.parquet')"
    assert (
        bench.normalise_paths(text, Path("/srv/clinvar_history"))
        == "read_parquet('$DATA_DIR/bench/a.parquet')"
    )


def test_machine_info_names_versions() -> None:
    info = bench.machine_info()
    assert {"cpu", "duckdb", "sqlite", "python", "os"} <= info.keys()
    assert info["duckdb"] == duckdb.__version__


def test_dictionary_lists_every_table_with_row_counts(file_warehouse: Paths) -> None:
    engine = connect(duckdb_path=file_warehouse.duckdb_path)
    text = render(engine)
    engine.close()
    for table in TABLES:
        assert f"## {table}\n" in text
    assert "| variant_key | VARCHAR | no |" in text
    # 10 ClinVar variations in the fixtures, one per line in variant_summary
    assert "Rows in the build described in the README: 10." in text
