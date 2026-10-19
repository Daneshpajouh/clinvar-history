# Contributing

Set up with `python3 -m venv .venv && .venv/bin/pip install -e ".[postgres,dev]"`,
then `make check` runs what CI runs: ruff (line length 100), ruff format,
mypy in strict mode, sqlfluff and pytest.

- Schema changes go in a new numbered file in `migrations/`. Never edit an
  applied migration; the runner refuses it.
- A new cookbook query needs a fixture row that exercises it and a test in
  `tests/test_queries.py` with the exact expected rows.
- A parsing change needs a unit test with the real edge case that prompted
  it (quote the source line in `tests/data/README.md`).
- Numbers in docs come from a run; give the command and date.
- Commit subjects are imperative and under 72 characters.
