# Changelog

The format follows Keep a Changelog; versions follow Semantic Versioning.

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
