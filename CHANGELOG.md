# Changelog

The format follows Keep a Changelog; versions follow Semantic Versioning.

## 1.0.1 - 2026-10-19

### Fixed

- `tests/data` was not committed: the ignore rule `data/` matched it as
  well as the top-level data folder, so in a fresh clone 1 test failed and
  25 errored. The rules for `data`, `site`, `build` and `dist` are now
  anchored to the repository root.
- Saved DuckDB plans named the build machine's data folder; `vwh bench` now
  writes paths relative to the data directory and the two committed plans
  show `$DATA_DIR`.
- A pipeline stage given as a one-word command raised `IndexError` instead
  of `FetchError` when it failed.
- `vwh fetch` no longer sets a custom curl user agent.

### Changed

- Data terms cite the gnomAD CC0 policy and the Ensembl disclaimer.
- Tests for the fetcher (curl faked), the benchmark and the data dictionary:
  77 tests, 92% line coverage on DuckDB and PostgreSQL.

## 1.0.0 - 2026-10-19

First release.

- Schema in five numbered migrations, shared by DuckDB and PostgreSQL;
  applied migrations are checksummed.
- ClinVar loads as one transaction per release, with the aggregate record as
  an SCD type 2 history and submissions kept per release; `vwh unload`
  removes the latest release.
- gnomAD v4.1 joint frequencies and MaveDB scores for ten genes.
- Eight cookbook queries, each tested on fixtures on both engines.
- Benchmarks for storage layout and engine choice, with plans.

### Data

- ClinVar 2025-10 and 2026-10, gnomAD v4.1 (joint), eight MaveDB score
  sets fetched 2026-10-19. Checksums in `docs/data_sources.md`.

### Fixed during development

- ClinVar load of the second release took 295 s in one upsert; now 2.7 s.
- Repeated SCV rows and AlleleIDs that move between VariationIDs no longer
  break the load. See `docs/operations/postmortems/`.
