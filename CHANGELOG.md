# Changelog

The format follows Keep a Changelog; versions follow Semantic Versioning.

## Unreleased

### Fixed

- PostgreSQL: a record whose `variant_key` passed the B-tree row limit of
  2,704 bytes stopped the load at the primary key. Migration 0008 keys
  `variant` by `variant_key_md5`, the md5 of the key, on both engines;
  `clinvar_variation` and `population_frequency` carry the digest for their
  foreign keys, a CHECK on each table ties it to the key, and PostgreSQL gets
  a hash index on `variant_key` for lookups. DuckDB rebuilds the three
  tables, because it cannot change a primary key in place. Cookbook query
  05 joins `population_frequency` on the digest, which leads its primary
  key, and the data dictionary lists the digest columns. A full load of
  both ClinVar releases with gnomAD and MaveDB now completes on PostgreSQL
  17.6 and passes all 18 validation checks; the README and
  `docs/performance.md` give the times (#1).
- A wheel install now works: the migrations, the cookbook queries, the
  default config and its schema moved into `src/clinvar_history/` and are
  read through `importlib.resources`. Before, the package read them from the
  checkout, so `pip install clinvar-history` then `migrate()` stopped with an
  error. Without a checkout the default data directory is `data/` in the
  working directory. CI builds the wheel, installs it in a fresh
  environment and runs a migrate, a fixture load and one query (#2).
- PostgreSQL: the loader role could not write `clinvar_variation_history`,
  because 0005 granted only the tables that existed when it ran. Migration
  0007 adds the grant and default privileges for later tables.

## 1.0.2 - 2026-10-19

### Changed

- Renamed from variant-warehouse to clinvar-history: Python package
  `clinvar_history`, command `clinvar-history`, environment variables
  `CLINVAR_HISTORY_*`, and PostgreSQL database and roles `clinvar_history*`.
  Migrations 0001, 0005 and 0006 changed with the names, so a database built
  with 1.0.1 has to be rebuilt; `migrate()` refuses an applied file whose
  checksum changed.
- The README opening states the PostgreSQL full-load limit, and the VUS to
  conflicting count is set beside clinvar-delta's.

## 1.0.1 - 2026-10-19

### Fixed

- `tests/data` was not committed: the ignore rule `data/` matched it as
  well as the top-level data folder, so in a fresh clone 1 test failed and
  25 errored. The rules for `data`, `site`, `build` and `dist` are now
  anchored to the repository root.
- Saved DuckDB plans named the build machine's data folder; `clinvar-history bench` now
  writes paths relative to the data directory and the two committed plans
  show `$DATA_DIR`.
- A pipeline stage given as a one-word command raised `IndexError` instead
  of `FetchError` when it failed.
- `clinvar-history fetch` no longer sets a custom curl user agent.
- `clinvar-history unload` did not undo the attribute values a release had overwritten
  in `clinvar_variation` (4,212 rows for 2026-10). Loads now keep them in
  `clinvar_variation_history` (migration 0006) and unload writes them back;
  on the full build the restored table matched the 2025-10 staging in every
  row. The unload test compares full table contents.
- Queries 04 and 05 read every loaded gnomAD release and every FILTER value.
  They now use the latest release, PASS sites only and AN >= 1000 in a group.
  CHEK2 c.1100del (FILTER `EXOMES_FILTERED`) drops out of query 05.
- Query 06 took the minimum of a key scored twice; it now takes the mean, and
  its header says VUS and conflicting records are set aside before the
  agreement check.
- `load_mavedb` raised `ValueError` when the manifest had no MaveDB files; it
  now logs and skips.
- A literal `%` in a parameterised query broke on PostgreSQL; it is doubled
  before psycopg sees it.
- DuckDB needs `pytz` to return timestamp-with-time-zone columns; it is now a
  dependency.
- The package description named ENCODE and HPRC, which are not loaded, and
  several documents said MaveDB covers ten genes (it covers seven).

### Changed

- Data terms cite the gnomAD CC0 policy and the Ensembl disclaimer.
- Tests for the fetcher (curl faked), the benchmark and the data dictionary,
  and a regression test for each fix above: 85 tests, 92% line coverage on
  DuckDB and PostgreSQL.
- `docs/results.md` holds the cookbook output of the full build.

## 1.0.0 - 2026-10-19

First release.

- Schema in five numbered migrations, shared by DuckDB and PostgreSQL;
  applied migrations are checksummed.
- ClinVar loads as one transaction per release, with the aggregate record as
  an SCD type 2 history and submissions kept per release; `clinvar-history unload`
  removes the latest release.
- gnomAD v4.1 joint frequencies for ten genes and eight MaveDB score sets
  covering seven of them.
- Eight cookbook queries, each tested on fixtures on both engines.
- Benchmarks for storage layout and engine choice, with plans.

### Data

- ClinVar 2025-10 and 2026-10, gnomAD v4.1 (joint), eight MaveDB score
  sets fetched 2026-10-19. Checksums in `docs/data_sources.md`.

### Fixed during development

- ClinVar load of the second release took 295 s in one upsert; now 2.7 s.
- Repeated SCV rows and AlleleIDs that move between VariationIDs no longer
  break the load. See `docs/operations/postmortems/`.
