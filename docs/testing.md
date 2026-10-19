# Testing

Three layers, each with one command.

| Layer | What it checks | Command |
| --- | --- | --- |
| Unit | parsing rules: class mapping, HGVS name parsing, variant class, PAR duplicates, repeated SCVs, missing VCF alleles, unparseable dates, MaveDB rows without HGVS | `pytest tests/test_staging.py` |
| Load and SQL | migrations, SCD history, idempotent reloads, release order, interrupted-refresh drill, unload, every cookbook query with exact expected rows | `pytest tests/test_load.py tests/test_queries.py tests/test_migrations.py` |
| End to end | the `vwh` command on the fixtures: load twice, validate, query, unload | `pytest tests/test_cli.py` |

The fixtures are hand-written and small enough to check by hand; each row
is described in `tests/data/README.md`, and the expected query results sit
next to the assertions in `tests/test_queries.py`.

The load and SQL layers run once per engine. Without `VWH_PG_DSN` they run
on an in-memory DuckDB; with it they run again on PostgreSQL, each test
module in its own schema:

```
docker compose up -d db
VWH_PG_DSN=postgresql://vwh:vwh@127.0.0.1:55432/vwh pytest -q --cov=vwh
```

Run on 2026-10-19 (macOS, PostgreSQL 17.6): 63 passed, 66% line coverage.

| Module | Coverage |
| --- | ---: |
| load.py | 99% |
| sources/clinvar.py | 98% |
| sources/gnomad.py | 96% |
| sources/mavedb.py | 100% |
| validate.py | 100% |
| db.py | 94% |
| cli.py | 73% |
| queries.py | 72% |
| fetch.py | 31% |
| bench.py | 0% |
| dictionary.py | 0% |

`fetch.py` and `bench.py` talk to remote services and to a database server
for minutes at a time; they were exercised by the real build described in
the README rather than by unit tests. The same suite ran inside the Docker
image (`docker build -t variant-warehouse:1.0.0 .`, Debian bookworm,
Python 3.13.9) against the PostgreSQL container: 63 passed in 5.68 s.

## The interrupted-refresh drill

`test_drill_interrupted_refresh_rolls_back` loads 2025-10, then starts the
2026-10 load and raises an exception after each of five steps in turn
(release row written, variations upserted, old classifications closed, new
ones opened, submissions written). After each crash it checks that every
table matches its state before the attempt, that `v_clinvar_release` still
reports 2025-10 as the latest release and `v_variant_current` still returns
its 7 records, and that a retry completes. This is a drill on fixtures; no
real load has been interrupted.
