"""Load the hand-written fixtures in tests/data into a throwaway data directory.

tests/data/README.md describes every row and why it is there. The test
modules list the expected result of each cookbook query on these rows.
"""

from __future__ import annotations

import gzip
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from vwh import load
from vwh.config import Paths
from vwh.db import Engine, connect, migrate
from vwh.fetch import record
from vwh.sources import clinvar, gnomad, mavedb

DATA = Path(__file__).parent / "data"
RELEASES = ["2025-10", "2026-10"]
GROUPS = ["afr", "nfe"]
SCORE_SETS = [
    {"urn": "urn:mavedb:00000097-0-2", "gene": "BRCA1", "match_level": "nucleotide"},
    {"urn": "urn:mavedb:00000068-0-1", "gene": "TP53", "match_level": "protein"},
]


def _gzip_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as fin, gzip.open(dest, "wb") as fout:
        shutil.copyfileobj(fin, fout)


def build_raw(paths: Paths) -> None:
    """Lay the fixtures out the way 'vwh fetch' would, manifest included."""
    for release in RELEASES:
        for kind in ("variant_summary", "submission_summary"):
            dest = paths.raw / "clinvar" / f"{kind}_{release}.txt.gz"
            _gzip_copy(DATA / f"{kind}_{release}.tsv", dest)
            record(
                paths,
                source="clinvar",
                release=release,
                url=f"fixture://{dest.name}",
                path=dest,
                method="fixture",
            )
    (paths.raw / "ensembl").mkdir(parents=True, exist_ok=True)
    shutil.copy(DATA / "genes.json", paths.raw / "ensembl" / "genes.json")
    gdest = paths.raw / "gnomad" / "gnomad.joint.v4.1.FIXTURE.vcf.gz"
    _gzip_copy(DATA / "gnomad.joint.v4.1.FIXTURE.vcf", gdest)
    record(
        paths, source="gnomad", release="4.1", url="fixture://gnomad", path=gdest, method="fixture"
    )
    for ss in SCORE_SETS:
        slug = ss["urn"].replace("urn:mavedb:", "")
        for name in (f"{slug}.json", f"{slug}.scores.csv"):
            dest = paths.raw / "mavedb" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(DATA / name, dest)
            record(
                paths,
                source="mavedb",
                release=ss["urn"],
                url=f"fixture://{name}",
                path=dest,
                method="fixture",
            )


def mave_config() -> list[dict[str, Any]]:
    return SCORE_SETS


def stage_all(paths: Paths) -> None:
    for release in RELEASES:
        clinvar.stage_release(paths.raw / "clinvar", paths.staging, release)
    gnomad.stage(paths.raw / "gnomad", paths.staging, GROUPS, "4.1")
    mavedb.stage(paths.raw / "mavedb", paths.staging, mave_config())


def load_all(engine: Engine, paths: Paths) -> None:
    migrate(engine)
    for release in sorted(RELEASES):
        load.load_clinvar(engine, paths, release)
    load.load_panel(engine, paths)
    load.load_gnomad(engine, paths, "4.1")
    load.load_mavedb(engine, paths)


@pytest.fixture(scope="session")
def fixture_paths(tmp_path_factory: pytest.TempPathFactory) -> Paths:
    paths = Paths(tmp_path_factory.mktemp("vwh-data"))
    build_raw(paths)
    stage_all(paths)
    return paths


def reset_postgres(dsn: str, schema: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


ENGINES = ["duckdb"] + (["postgres"] if os.environ.get("VWH_PG_DSN") else [])


@pytest.fixture(params=ENGINES)
def empty_engine(request: pytest.FixtureRequest) -> Iterator[Engine]:
    if request.param == "postgres":
        dsn = os.environ["VWH_PG_DSN"]
        reset_postgres(dsn, "vwh_test_empty")
        engine = connect(dsn=dsn, schema="vwh_test_empty")
    else:
        engine = connect()
    yield engine
    engine.close()


@pytest.fixture(scope="session", params=ENGINES)
def loaded_engine(request: pytest.FixtureRequest, fixture_paths: Paths) -> Iterator[Engine]:
    if request.param == "postgres":
        dsn = os.environ["VWH_PG_DSN"]
        reset_postgres(dsn, "vwh_test_loaded")
        engine = connect(dsn=dsn, schema="vwh_test_loaded")
    else:
        engine = connect()
    load_all(engine, fixture_paths)
    yield engine
    engine.close()
