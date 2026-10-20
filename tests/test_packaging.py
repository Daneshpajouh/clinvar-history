"""The migrations, cookbook queries, default config and schema ship inside the package."""

from __future__ import annotations

import tomllib
from fnmatch import fnmatchcase
from importlib.resources import files
from pathlib import Path

from clinvar_history import config

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "src" / "clinvar_history"


def test_data_files_are_read_from_the_package() -> None:
    package = Path(str(files("clinvar_history")))
    for path in (config.DEFAULT_CONFIG, config.SCHEMA_PATH):
        assert path.is_file(), path
        assert package in path.parents, path
    assert sorted((package / "migrations").glob("0001_*.sql"))
    assert sorted((package / "sql" / "queries").glob("01_*.sql"))


def _shipped(relative: str, globs: list[str]) -> bool:
    # setuptools globs start at the package folder and * stops at a /.
    return any(fnmatchcase(relative, g) and relative.count("/") == g.count("/") for g in globs)


def test_package_data_globs_cover_every_data_file() -> None:
    # A file under the package that no package-data glob matches is left out of the wheel.
    # Dotfiles (.sqlfluff, a Finder .DS_Store) are not package data.
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    globs = pyproject["tool"]["setuptools"]["package-data"]["clinvar_history"]
    left_out = [
        rel
        for p in PACKAGE_DIR.rglob("*")
        if p.is_file()
        and p.suffix not in (".py", ".pyc")
        and not p.name.startswith(".")
        and not _shipped(rel := p.relative_to(PACKAGE_DIR).as_posix(), globs)
    ]
    assert left_out == []


def test_package_data_globs_start_at_the_package_folder() -> None:
    globs = ["schemas/*.json"]
    assert _shipped("schemas/config.schema.json", globs)
    assert not _shipped("sources/schemas/config.schema.json", globs)
