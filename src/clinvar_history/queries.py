"""Run cookbook SQL files and print results."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from clinvar_history.config import PACKAGE_DATA
from clinvar_history.db import Engine

QUERY_DIR = PACKAGE_DATA / "sql" / "queries"


def resolve(name: str) -> Path:
    path = Path(name)
    if path.suffix == ".sql" and path.exists():
        return path
    matches = sorted(QUERY_DIR.glob(f"{name}*.sql"))
    if len(matches) != 1:
        raise FileNotFoundError(f"{name!r} matches {len(matches)} files in {QUERY_DIR}")
    return matches[0]


def run(engine: Engine, name: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    return engine.query(resolve(name).read_text())


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (int, str, bool)):
        return value
    if isinstance(value, float):
        return round(value, 6)
    try:
        return float(value)  # Decimal from PostgreSQL numeric
    except (TypeError, ValueError):
        return str(value)


def print_result(cols: list[str], rows: list[tuple[Any, ...]], fmt: str, limit: int) -> None:
    if fmt == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow(cols)
        writer.writerows([[_plain(v) for v in r] for r in rows])
    elif fmt == "json":
        print(json.dumps([dict(zip(cols, map(_plain, r), strict=True)) for r in rows], indent=1))
    else:
        table = Table(*cols)
        for r in rows[:limit]:
            table.add_row(*["" if v is None else str(_plain(v)) for v in r])
        Console().print(table)
        if len(rows) > limit:
            print(f"... {len(rows) - limit} more rows")
