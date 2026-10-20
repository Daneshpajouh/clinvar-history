# Testing

Four layers, each with one command.

| Layer | What it checks | Command |
| --- | --- | --- |
| Unit | parsing rules: class mapping, HGVS name parsing, variant class, PAR duplicates, repeated SCVs, missing VCF alleles, unparseable dates, MaveDB rows without HGVS | `pytest tests/test_staging.py` |
| Load and SQL | migrations, SCD history, idempotent reloads, release order, interrupted-refresh drill, unload compared row for row with the state before the release, latest-release and PASS rules for gnomAD, every cookbook query with exact expected rows | `pytest tests/test_load.py tests/test_queries.py tests/test_migrations.py` |
| End to end | the `clinvar-history` command on the fixtures: load twice, validate, query, unload | `pytest tests/test_cli.py` |
| Fetch and bench | downloads with curl and bcftools faked (failed and short transfers, truncated gzip, wrong assembly, manifest), a one-repeat benchmark on the fixture warehouse, the generated data dictionary | `pytest tests/test_fetch.py tests/test_bench.py` |

The fixtures are hand-written and small enough to check by hand; each row
is described in `tests/data/README.md`, and the expected query results sit
next to the assertions in `tests/test_queries.py`.

The load and SQL layers run once per engine. Without `CLINVAR_HISTORY_PG_DSN` they run
on an in-memory DuckDB; with it they run again on PostgreSQL, in two schemas: one for the tests
that start from an empty database and one for the loaded fixtures:

```
docker compose up -d db
CLINVAR_HISTORY_PG_DSN=postgresql://clinvar_history:clinvar_history@127.0.0.1:55432/clinvar_history .venv/bin/pytest -q --cov=clinvar_history
```

Run on 2026-10-19 (macOS, PostgreSQL 17.6): 85 passed, 92% line coverage
(60 tests without `CLINVAR_HISTORY_PG_DSN`).

| Module | Coverage |
| --- | ---: |
| load.py | 99% |
| sources/clinvar.py | 98% |
| sources/gnomad.py | 96% |
| sources/mavedb.py | 100% |
| validate.py | 100% |
| db.py | 94% |
| fetch.py | 94% |
| bench.py | 99% |
| dictionary.py | 100% |
| cli.py | 73% |
| queries.py | 72% |
| logs.py | 86% |
| config.py | 98% |

Not covered: in `cli.py`, the `fetch`, `bench`, `dictionary` and `version`
commands (their library functions are tested directly), the load-failure
branch and the gnomAD and MaveDB branches of `stage`; in `queries.py`, the
CSV and table printers.

## The interrupted-refresh drill

`test_drill_interrupted_refresh_rolls_back` loads 2025-10, then starts the
2026-10 load and raises an exception after each of five steps in turn
(release row written, variations upserted, old classifications closed, new
ones opened, submissions written). After each crash it checks that every
table matches its state before the attempt row for row, that `v_clinvar_release` still
reports 2025-10 as the latest release and `v_variant_current` still returns
its 7 records, and that a retry completes. This is a drill on fixtures; no
real load has been interrupted.
