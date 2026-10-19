# Changelog

The format follows Keep a Changelog; versions follow Semantic Versioning.

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
