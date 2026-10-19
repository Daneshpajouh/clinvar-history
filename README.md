# variant-warehouse

A versioned SQL database of human variant interpretations built from public
releases: ClinVar (two monthly releases, genome-wide), gnomAD v4.1 allele
frequencies for ten hereditary cancer genes, and MaveDB functional scores
(eight score sets covering seven of those genes). It runs on DuckDB for a
single analyst and on PostgreSQL for shared use, from the same migrations and
the same queries.

## Why

ClinVar changes every month. Between the 2025-10 and 2026-10 releases, 20,364
variants went from "uncertain significance" to "conflicting classifications",
and 1,415 went from uncertain to pathogenic or likely pathogenic. A lab that
reports variants needs to answer "what did ClinVar say when we signed this
report, and what does it say now?", and to check a classification against
population frequency and functional assays. That needs every release kept,
loads that cannot half-finish, and a record of which file each row came from.
`docs/explainer.md` covers the background for readers outside genomics.

## Quick start (fixtures, under a minute)

```
git clone <this repository> && cd variant-warehouse
python3 -m venv .venv && .venv/bin/pip install -e ".[postgres,dev]"
.venv/bin/pytest -q
```

```
60 passed in 2.76s
```

With a PostgreSQL server the same suite runs a second time against it
(`docker compose up -d db`, then
`VWH_PG_DSN=postgresql://vwh:vwh@127.0.0.1:55432/vwh .venv/bin/pytest -q`: 85 passed in
5.58 s).
The Docker image runs the same 63 tests on Debian:
`docker build -t variant-warehouse:1.0.0 .` then
`docker run --rm -e VWH_PG_DSN=... --entrypoint python variant-warehouse:1.0.0 -m pytest -q`
(63 passed in 5.68 s on 2026-10-19).

## Full build (real data)

Needs Python 3.11 or newer, curl, bcftools (gnomAD is read by region from the
remote VCF) and about 6 GB free in the data directory: 1.60 GB of raw files,
0.59 GB of staging Parquet and a 3.4 GB DuckDB file in the 2026-10-19 build.

```
export VWH_DATA_DIR=/path/with/5GB/free
vwh fetch genes && vwh fetch clinvar && vwh fetch gnomad && vwh fetch mavedb
vwh stage clinvar && vwh stage gnomad && vwh stage mavedb
vwh load            # add --dsn postgresql://... for PostgreSQL
vwh validate
vwh query 03        # reclassifications between the two releases
```

Measured on 2026-10-19 (Apple M3 Ultra, 96 GB, macOS, DuckDB 1.5.6, 6 threads):
31 input files, 1.60 GB. `vwh stage` took 51.6 s for both ClinVar releases,
8.3 s for gnomAD and 0.8 s for MaveDB. `vwh load`
took 115 s wall time with a 6.9 GB peak memory footprint and produced a 3.7 GB
DuckDB file.

| Table | Rows |
| --- | ---: |
| clinvar_variation | 4,584,619 |
| classification (SCD type 2 versions) | 5,416,637 |
| submission (both releases) | 12,257,320 |
| variant | 4,919,816 |
| population_frequency | 4,243,184 |
| functional_score | 71,644 |

All 18 validation checks passed (`docs/validation.md`); query output is in
`docs/results.md`.

## What is in it

- `migrations/`: numbered SQL files applied in order and recorded with their
  SHA-256 in `schema_migrations`; an edited, already-applied file stops the
  run. Files ending `.postgres.sql` hold the foreign keys DuckDB cannot keep
  and the read-only analyst role.
- `src/vwh/`: the `vwh` command (fetch, stage, load, unload, validate, query,
  bench, dictionary). Staging uses polars; loading is SQL.
- `sql/queries/`: eight cookbook queries, each tested on fixtures on both
  engines.
- `tests/`: unit tests for every parsing rule, the cookbook tests, and the
  interrupted-refresh drill. Fixtures are hand-written in `tests/data`.
- `docs/`: ER diagram, data dictionary, refresh SOP, code walk-through,
  testing, logging, performance, operations runbook and a postmortem.

Design notes:

- ClinVar's aggregate record (`classification`) and the individual submissions
  (`submission`) are separate tables. A class change in the aggregate is a new
  SCD row valid from that release; the old row is closed, not overwritten.
- A release load is one transaction. `tests/test_load.py` crashes it after
  each of five steps and checks that the previous release is still what
  analysts see. `vwh unload` removes the latest release and writes back the
  variation attributes it overwrote; on the full build it restored the 4,212
  overwritten rows (0 rows differing from the 2025-10 staging) in 261 s.
- ClinVar and gnomAD join on the GRCh38 key `chrom-pos-ref-alt` built from
  their VCF columns. Both are GRCh38 and left-aligned; there is no liftover
  anywhere in the warehouse.

## Limits

- A full PostgreSQL load will stop at the primary key on
  `variant.variant_key`: a B-tree cannot hold the longest ClinVar alleles. The
  benchmark's index on the same values failed with "index row size 2880
  exceeds btree version 4 maximum 2704"; the full load itself has not been
  run. The PostgreSQL path is tested on fixtures and benchmarked on a flat
  4.56 million-row table. `ROADMAP.md` item 1 replaces the key.
- gnomAD covers the ten panel genes and MaveDB seven of them; ClinVar is
  genome-wide. A MaveDB load replaces the score sets it names and keeps no
  history of earlier fetches.
- MaveDB protein-level matches use only ClinVar records with at least one
  star and class P/LP or B/LB, and need all of them to agree; see
  `sql/queries/06_mave_concordance.sql`.

Licence: Apache-2.0 for the code. Each data source has its own terms,
listed in `docs/data_sources.md`.
