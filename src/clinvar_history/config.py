"""Build configuration: YAML file checked against a JSON Schema."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "config.yaml"
SCHEMA_PATH = REPO_ROOT / "workflow" / "schemas" / "config.schema.json"


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
    if SCHEMA_PATH.exists():
        schema = json.loads(SCHEMA_PATH.read_text())
        jsonschema.validate(cfg, schema)
    return cfg


def data_paths(data_dir: str | Path | None = None) -> Paths:
    base = data_dir or os.environ.get("CLINVAR_HISTORY_DATA_DIR") or (REPO_ROOT / "data")
    return Paths(Path(base))
