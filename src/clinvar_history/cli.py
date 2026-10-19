"""clinvar_history: fetch, stage, load, unload, validate, query, bench and dictionary."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import duckdb
import typer

from clinvar_history import __version__
from clinvar_history.config import data_paths, load_config
from clinvar_history.db import Engine, connect, migrate
from clinvar_history.load import LoadError
from clinvar_history.logs import get_logger, setup_logging

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)
log = get_logger("clinvar_history")

ConfigOpt = Annotated[Path | None, typer.Option("--config", help="YAML build config")]
DataDirOpt = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Data directory (default CLINVAR_HISTORY_DATA_DIR or ./data)"),
]
DsnOpt = Annotated[
    str | None,
    typer.Option("--dsn", help="PostgreSQL DSN; omit to use the DuckDB file in the data directory"),
]

SOURCES = ["genes", "clinvar", "gnomad", "mavedb"]

PG_ERRORS: tuple[type[Exception], ...] = ()
try:  # psycopg is optional: only the PostgreSQL path needs it
    import psycopg

    PG_ERRORS = (psycopg.Error,)
except ImportError:
    pass
LOAD_ERRORS: tuple[type[Exception], ...] = (LoadError, OSError, duckdb.Error, *PG_ERRORS)
TABLE_COUNTS = [
    "source_release",
    "provenance",
    "gene",
    "variant",
    "clinvar_variation",
    "classification",
    "submitter",
    "submission",
    "population_frequency",
    "score_set",
    "functional_score",
]


@app.callback()
def main(
    log_level: Annotated[str, typer.Option(help="DEBUG, INFO, WARNING")] = "INFO",
    log_file: Annotated[str | None, typer.Option(help="Also write JSON log lines here")] = None,
) -> None:
    setup_logging(log_level, log_file)


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def fetch(
    source: Annotated[str, typer.Argument(help=f"One of: {', '.join(SOURCES)}")],
    release: Annotated[str | None, typer.Option(help="ClinVar release, YYYY-MM")] = None,
    config: ConfigOpt = None,
    data_dir: DataDirOpt = None,
) -> None:
    """Download one source into <data_dir>/raw and append to the manifest."""
    from clinvar_history import fetch as f

    cfg = load_config(config)
    paths = data_paths(data_dir)
    if source == "clinvar":
        releases = [release] if release else cfg["clinvar"]["releases"]
        for rel in releases:
            f.fetch_clinvar(cfg, paths, rel)
    elif source == "genes":
        f.fetch_genes(cfg, paths)
    elif source == "gnomad":
        f.fetch_gnomad(cfg, paths)
    elif source == "mavedb":
        f.fetch_mavedb(cfg, paths)
    else:
        raise typer.BadParameter(f"unknown source {source!r}")


def _engine(dsn: str | None, data_dir: Path | None) -> Engine:
    paths = data_paths(data_dir)
    return connect(dsn=dsn, duckdb_path=paths.duckdb_path)


@app.command()
def stage(
    source: Annotated[str, typer.Argument(help="clinvar, gnomad or mavedb")],
    release: Annotated[str | None, typer.Option(help="ClinVar release, YYYY-MM")] = None,
    config: ConfigOpt = None,
    data_dir: DataDirOpt = None,
) -> None:
    """Parse raw files into typed Parquet under <data_dir>/staging."""
    from clinvar_history.sources import clinvar, gnomad, mavedb

    cfg = load_config(config)
    paths = data_paths(data_dir)
    if source == "clinvar":
        for rel in [release] if release else cfg["clinvar"]["releases"]:
            clinvar.stage_release(paths.raw / "clinvar", paths.staging, rel)
    elif source == "gnomad":
        gnomad.stage(
            paths.raw / "gnomad",
            paths.staging,
            cfg["gnomad"]["ancestry_groups"],
            cfg["gnomad"]["release"],
        )
    elif source == "mavedb":
        mavedb.stage(paths.raw / "mavedb", paths.staging, cfg["mavedb"]["score_sets"])
    else:
        raise typer.BadParameter(f"unknown source {source!r}")


@app.command()
def load(
    source: Annotated[str, typer.Argument(help="all, clinvar, gnomad or mavedb")] = "all",
    release: Annotated[str | None, typer.Option(help="ClinVar release, YYYY-MM")] = None,
    config: ConfigOpt = None,
    data_dir: DataDirOpt = None,
    dsn: DsnOpt = None,
) -> None:
    """Apply migrations, then load staged data. Re-running with the same files is a no-op."""
    import time

    from clinvar_history import load as ld
    from clinvar_history import validate as val
    from clinvar_history.fetch import read_manifest

    cfg = load_config(config)
    paths = data_paths(data_dir)
    engine = _engine(dsn, data_dir)
    started = time.monotonic()
    applied = migrate(engine)
    schema_version = engine.scalar("SELECT max(filename) FROM schema_migrations")
    for row in read_manifest(paths):
        if row["source"] in ("clinvar", "gnomad", "mavedb") and source in ("all", row["source"]):
            log.info(
                "input", extra={k: row[k] for k in ("source", "release", "url", "path", "sha256")}
            )
    log.info(
        "load start",
        extra={
            "target": engine.name,
            "schema_version": schema_version,
            "migrations_applied": applied,
            "source": source,
        },
    )
    try:
        if source in ("all", "clinvar"):
            for rel in [release] if release else sorted(cfg["clinvar"]["releases"]):
                ld.load_clinvar(engine, paths, rel)
            ld.load_panel(engine, paths)
        if source in ("all", "gnomad"):
            ld.load_gnomad(engine, paths, cfg["gnomad"]["release"])
        if source in ("all", "mavedb"):
            ld.load_mavedb(engine, paths)
    except LOAD_ERRORS as exc:
        # The release transaction has already rolled back; log and exit non-zero.
        log.error("load failed", extra={"error": str(exc), "error_type": type(exc).__name__})
        engine.close()
        raise typer.Exit(1) from exc
    counts = {t: engine.scalar(f"SELECT count(*) FROM {t}") for t in TABLE_COUNTS}
    results = val.run_checks(engine)
    failed = [r.name for r in results if not r.passed]
    log.info(
        "load summary",
        extra={
            "status": "ok" if not failed else "validation_failed",
            "seconds": round(time.monotonic() - started, 1),
            "rows": counts,
            "checks_passed": len(results) - len(failed),
            "checks_failed": failed,
        },
    )
    engine.close()
    if failed:
        raise typer.Exit(1)


@app.command()
def unload(
    source: Annotated[str, typer.Argument(help="clinvar")] = "clinvar",
    data_dir: DataDirOpt = None,
    dsn: DsnOpt = None,
) -> None:
    """Roll back the most recent ClinVar release in one transaction."""
    from clinvar_history import load as ld

    if source != "clinvar":
        raise typer.BadParameter("only the latest ClinVar release can be unloaded")
    engine = _engine(dsn, data_dir)
    label = ld.unload_latest_clinvar(engine)
    typer.echo(f"unloaded clinvar {label}" if label else "nothing to unload")
    engine.close()


@app.command()
def validate(
    data_dir: DataDirOpt = None,
    dsn: DsnOpt = None,
    report: Annotated[Path | None, typer.Option(help="Write a Markdown report here")] = None,
) -> None:
    """Run the validation checks; exit 1 if any check fails."""
    from clinvar_history import validate as val

    engine = _engine(dsn, data_dir)
    results = val.run_checks(engine)
    engine.close()
    for r in results:
        typer.echo(f"{'PASS' if r.passed else 'FAIL'}  {r.name}: {r.detail}")
    if report:
        report.write_text(val.to_markdown(results, engine_name=engine.name))
    if not all(r.passed for r in results):
        raise typer.Exit(1)


@app.command()
def query(
    name: Annotated[str, typer.Argument(help="File stem in sql/queries, or a path to a .sql file")],
    data_dir: DataDirOpt = None,
    dsn: DsnOpt = None,
    fmt: Annotated[str, typer.Option("--format", help="table, csv or json")] = "table",
    limit: Annotated[int, typer.Option(help="Rows to print in table format")] = 50,
) -> None:
    """Run a cookbook query and print the result."""
    from clinvar_history import queries

    engine = _engine(dsn, data_dir)
    cols, rows = queries.run(engine, name)
    engine.close()
    queries.print_result(cols, rows, fmt, limit)


@app.command()
def bench(
    data_dir: DataDirOpt = None,
    dsn: DsnOpt = None,
    repeats: Annotated[int, typer.Option(help="Timed runs per case")] = 5,
    out: Annotated[Path, typer.Option(help="CSV with one row per timed case")] = Path(
        "bench/results/latest.csv"
    ),
    plans: Annotated[Path, typer.Option(help="Folder for EXPLAIN ANALYZE output")] = Path(
        "bench/plans"
    ),
) -> None:
    """Time the benchmark cases on DuckDB, SQLite and (with --dsn) PostgreSQL."""
    from clinvar_history import bench as bm

    paths = data_paths(data_dir)
    rows = bm.run_all(paths, dsn=dsn, repeats=repeats, plans=plans)
    bm.write_csv(rows, out)
    typer.echo(json.dumps(bm.machine_info(), indent=1))


@app.command()
def dictionary(
    data_dir: DataDirOpt = None,
    out: Annotated[Path, typer.Option(help="Markdown output")] = Path("docs/data_dictionary.md"),
) -> None:
    """Regenerate the data dictionary from the loaded DuckDB catalogue."""
    from clinvar_history.dictionary import render

    engine = _engine(None, data_dir)
    out.write_text(render(engine))
    engine.close()


if __name__ == "__main__":
    sys.exit(app())
