# clinvar-history

A versioned SQL database of human variant interpretations built from public
releases: ClinVar (two monthly releases, genome-wide), gnomAD v4.1 allele
frequencies for ten hereditary cancer genes, and MaveDB functional scores
(eight score sets covering seven of those genes). It runs on DuckDB for a
single analyst. The same migrations and queries pass the test suite on
PostgreSQL, but a full PostgreSQL load is blocked by one primary key (see
Limits).

## Why

ClinVar changes every month. Between the 2025-10 and 2026-10 monthly
`variant_summary` releases, 20,364 variants went from "uncertain significance"
to "conflicting classifications", and 1,415 went from uncertain to pathogenic
or likely pathogenic. (clinvar-delta counts 19,907 VUS to conflicting from
the weekly GRCh38 VCFs of 2025-10-13 and 2026-10-11; the files and dates
differ.) A lab that
reports variants needs to answer "what did ClinVar say when we signed this
report, and what does it say now?", and to check a classification against
population frequency and functional assays. That needs every release kept,
loads that cannot half-finish, and a record of which file each row came from.
`docs/explainer.md` covers the background for readers outside genomics.

## Quick start (fixtures, under a minute)

```
git clone https://github.com/Daneshpajouh/clinvar-history && cd clinvar-history
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[postgres,dev]"
pytest -q
```

```
62 passed, 1 skipped in 2.85s
```

With a PostgreSQL server the same suite runs a second time against it
(`docker compose up -d db`, then
`CLINVAR_HISTORY_PG_DSN=postgresql://clinvar_history:clinvar_history@127.0.0.1:55432/clinvar_history pytest -q`: 89 passed and
1 skipped in 6.39 s).
The Docker image carries the tests too:
`docker build -t clinvar-history:1.0.2 .` then
`docker run --rm -e CLINVAR_HISTORY_PG_DSN=... --entrypoint python clinvar-history:1.0.2 -m pytest -q`
(85 passed in 6.79 s on 2026-10-19 with the 1.0.1 image, built from a fresh
clone). CI builds the image and runs `clinvar-history version` through its
default entrypoint; tagged releases publish it as
`ghcr.io/daneshpajouh/clinvar-history` after the tests pass.

## Full build (real data)

Needs Python 3.11 or newer (CI tests 3.11 and 3.13) with the quick start's
venv active, curl, bcftools (gnomAD is read by region from the remote VCF)
and about 6 GB free in the data directory: 1.60 GB of raw files,
0.59 GB of staging Parquet and a 3.4 GB DuckDB file in the 2026-10-19 build.

```
export CLINVAR_HISTORY_DATA_DIR=/path/with/6GB/free
clinvar-history fetch genes && clinvar-history fetch clinvar && clinvar-history fetch gnomad && clinvar-history fetch mavedb
clinvar-history stage clinvar && clinvar-history stage gnomad && clinvar-history stage mavedb
clinvar-history load            # --dsn postgresql://... for PostgreSQL; a full load fails there (Limits)
clinvar-history validate
clinvar-history query 03        # reclassifications between the two releases
```

Measured on 2026-10-19 (Apple M3 Ultra, 96 GB, macOS, DuckDB 1.5.6, 6 threads):
31 input files, 1.60 GB. `clinvar-history stage` took 51.6 s for both ClinVar releases,
8.3 s for gnomAD and 0.8 s for MaveDB. `clinvar-history load`
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
  and the analyst and loader roles.
- `src/clinvar_history/`: the `clinvar-history` command (fetch, stage, load, unload, validate, query,
  bench, dictionary). Staging uses polars; loading is SQL.
- `sql/queries/`: eight cookbook queries, each tested on fixtures on both
  engines.
- `tests/`: parsing tests, the cookbook tests, and the
  interrupted-refresh drill. Fixtures are hand-written in `tests/data`.
- `docs/`: ER diagram, data dictionary, refresh SOP, testing, logging,
  performance, operations runbook and the postmortem of the 2026-10-19 build.

Design notes:

- ClinVar's aggregate record (`classification`) and the individual submissions
  (`submission`) are separate tables. A class change in the aggregate is a new
  SCD row valid from that release; the old row is closed, not overwritten.
- A release load is one transaction. `tests/test_load.py` crashes it after
  each of five steps and checks that the previous release is still what
  analysts see. `clinvar-history unload` removes the latest release and writes back the
  variation attributes it overwrote; on the full build it restored the 4,212
  overwritten rows (0 rows differing from the 2025-10 staging) in 261 s.
- Engine differences stay in `db.py` (parameter style, Parquet staging
  through COPY on PostgreSQL) and the `.postgres.sql` migrations. The
  queries use only SQL both engines accept: CTEs, window functions with a
  named `WINDOW`, `percentile_cont ... WITHIN GROUP`, `IS DISTINCT FROM`
  and `UPDATE ... FROM`.
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
- Install from a checkout with `pip install -e`: the package reads
  `config/`, `migrations/`, `sql/` and `workflow/schemas/` from the
  repository, and a wheel install carries none of them (`migrate()` then
  stops with an error).
- gnomAD covers the ten panel genes and MaveDB seven of them; ClinVar is
  genome-wide. A MaveDB load replaces the score sets it names and keeps no
  history of earlier fetches.
- MaveDB protein-level matches use only ClinVar records with at least one
  star and class P/LP or B/LB, and need all of them to agree; see
  `sql/queries/06_mave_concordance.sql`.

Licence: Apache-2.0 for the code. Each data source has its own terms,
listed in `docs/data_sources.md`.
