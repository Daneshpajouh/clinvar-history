# Code walk-through

Read in this order; each file is short.

1. `config/config.yaml` and `workflow/schemas/config.schema.json`: which
   releases, genes and score sets make a build. `vwh.config.load_config`
   rejects a config that does not match the schema.
2. `src/vwh/fetch.py`: downloads with curl, checks the exit code before
   anything else, writes through a `.part` file, compares the size with the
   server's, and appends a manifest row with the SHA-256. gnomAD is read by
   region from the remote VCF with bcftools, keeping 45 INFO fields.
3. `src/vwh/sources/clinvar.py`: polars parsing of the two ClinVar files.
   The rules worth reading are `clinsig_class` (only exact strings map to
   P/LP, B/LB, VUS or Conflicting), the `NAME_RE` split of the HGVS name, the
   chrX-over-chrY choice for pseudoautosomal duplicates, and the repeated SCV
   handling. `gnomad.py` and `mavedb.py` follow the same pattern.
4. `migrations/`: the schema. `0001` holds the tables, `0002` the review
   status stars and ancestry groups, `0003` the analyst views,
   `0004` and `0005` PostgreSQL-only foreign keys and roles. `db.migrate`
   applies them and refuses an edited file that was already applied.
5. `src/vwh/load.py`: one transaction per release. `load_clinvar` is the
   core: genes, variants, changed variations, then the SCD type 2 step
   (close current rows whose aggregate record changed or disappeared, open
   rows for new or changed records), then submissions and provenance.
   `unload_latest_clinvar` removes the release's rows, reopens the versions
   it closed and writes back overwritten variation attributes from
   `clinvar_variation_history`; gene rows and variant keys it added stay.
6. `src/vwh/validate.py`: checks as SQL counts that must be zero.
7. `sql/queries/`: the cookbook. `06_mave_concordance.sql` is the longest:
   it labels each functional score only when all matching ClinVar variants
   agree, computes average ranks with two window functions and turns the
   rank sum into a Mann-Whitney AUC.
8. `tests/`: `conftest.py` builds a data directory from `tests/data` and
   loads it on each engine; `test_load.py` holds the interrupted-refresh
   drill.

Engine differences are confined to `db.py` (parameter style, Parquet
staging through COPY on PostgreSQL) and to the two `.postgres.sql`
migrations. The queries use only SQL both engines accept: CTEs, window
functions with a named `WINDOW`, `percentile_cont ... WITHIN GROUP`,
`IS DISTINCT FROM`, `UPDATE ... FROM`.
