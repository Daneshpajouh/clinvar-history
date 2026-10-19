"""The vwh command end to end on the fixtures: load, rerun, validate, query, unload."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from vwh.cli import app
from vwh.config import Paths

runner = CliRunner()


def test_load_validate_query_unload(fixture_paths: Paths) -> None:
    data = ["--data-dir", str(fixture_paths.data_dir)]
    first = runner.invoke(app, ["load", *data])
    assert first.exit_code == 0, first.output
    # A second load finds every release already recorded and changes nothing.
    again = runner.invoke(app, ["load", *data])
    assert again.exit_code == 0, again.output

    report = fixture_paths.data_dir / "validation.md"
    checked = runner.invoke(app, ["validate", *data, "--report", str(report)])
    assert checked.exit_code == 0, checked.output
    assert "FAIL" not in checked.output
    assert "| pass |" in report.read_text()

    out = runner.invoke(app, ["query", "03", *data, "--format", "json"])
    assert out.exit_code == 0, out.output
    assert json.loads(out.output) == [{"from_class": "VUS", "to_class": "P/LP", "variations": 1}]

    gone = runner.invoke(app, ["unload", *data])
    assert gone.output.strip().endswith("unloaded clinvar 2026-10")
    after = runner.invoke(app, ["query", "03", *data, "--format", "json"])
    assert json.loads(after.output) == []  # one ClinVar release left, nothing to compare


def test_unknown_source_is_rejected(fixture_paths: Paths) -> None:
    result = runner.invoke(app, ["stage", "encode", "--data-dir", str(fixture_paths.data_dir)])
    assert result.exit_code != 0
