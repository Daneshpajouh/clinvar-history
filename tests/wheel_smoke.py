"""Smoke test for an installed wheel: migrate, load the fixtures, run one query.

CI installs the built wheel in a fresh environment outside the checkout and runs
this as `python -m tests.wheel_smoke` from the checkout root. src/ is not on
sys.path then, so the package, its migrations and its queries come from the
wheel. Not collected by pytest (the name has no test_ prefix).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import clinvar_history
from clinvar_history import queries
from clinvar_history.config import Paths
from clinvar_history.db import connect

from .conftest import build_raw, load_all, stage_all

CHECKOUT = Path(__file__).resolve().parents[1]
# The same rows as test_queries.test_review_star_distribution.
EXPECTED = [
    (3, 1, 11.11, 11.11),
    (2, 2, 22.22, 33.33),
    (1, 5, 55.56, 88.89),
    (0, 1, 11.11, 100.0),
]


def main() -> int:
    installed = Path(clinvar_history.__file__).resolve()
    if CHECKOUT in installed.parents:
        print(f"clinvar_history was imported from the checkout: {installed}", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        paths = Paths(Path(tmp))
        build_raw(paths)
        stage_all(paths)
        engine = connect()  # in-memory DuckDB
        load_all(engine, paths)  # applies the packaged migrations first
        _, result = queries.run(engine, "02_review_star_distribution")
        engine.close()
    got = [tuple(queries._plain(v) for v in r) for r in result]
    if got != EXPECTED:
        print(f"02_review_star_distribution gave {got}, expected {EXPECTED}", file=sys.stderr)
        return 1
    print(f"wheel at {installed.parent}: migrations applied, 02_review_star_distribution matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
