"""Build configuration: YAML file checked against a JSON Schema."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
# Migrations, cookbook queries, the default config and its schema ship inside the
# package, so an installed wheel has them as well as a checkout.
PACKAGE_DATA = Path(str(files("clinvar_history")))
DEFAULT_CONFIG = PACKAGE_DATA / "defaults" / "config.yaml"
SCHEMA_PATH = PACKAGE_DATA / "schemas" / "config.schema.json"


@dataclass(frozen=True)
class Paths:
    data_dir: Path

    @property
    def raw(self) -> Path:
        return self.data_dir / "raw"

    @property
    def staging(self) -> Path:
        return self.data_dir / "staging"

    @property
    def manifest(self) -> Path:
        return self.raw / "manifest.jsonl"

    @property
    def duckdb_path(self) -> Path:
        return self.data_dir / "db" / "warehouse.duckdb"

    @property
    def reports(self) -> Path:
        return self.data_dir / "reports"


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or DEFAULT_CONFIG
    with cfg_path.open() as fh:
        cfg: dict[str, Any] = yaml.safe_load(fh)
    jsonschema.validate(cfg, json.loads(SCHEMA_PATH.read_text()))
    return cfg


def data_paths(data_dir: str | Path | None = None) -> Paths:
    base = data_dir or os.environ.get("CLINVAR_HISTORY_DATA_DIR") or _default_data_dir()
    return Paths(Path(base))


def _default_data_dir() -> Path:
    # A checkout keeps data/ beside pyproject.toml; an installed package has no
    # checkout around it, so it uses data/ in the working directory.
    if (REPO_ROOT / "pyproject.toml").exists():
        return REPO_ROOT / "data"
    return Path.cwd() / "data"
