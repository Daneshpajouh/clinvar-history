# Runbook

Each entry: symptom, how to confirm, what to do. Commands assume
`VWH_DATA_DIR` is set and logs go to a file with `--log-file`.

## Failed load

Symptom: `vwh load` exits 1 with a `load failed` log line.

The release transaction has rolled back; analysts still see the previous
release. Confirm with `vwh query 02` (it returns) and
`SELECT label, status FROM source_release` (no `loading` row). Read
`error` in the log line: a constraint name and key point at the data
(examples in `postmortems/2026-10-19-clinvar-refresh-build.md`); an I/O error
points at disk or network. Fix and rerun the same command; loads of
releases already recorded with the same SHA-256 are skipped.

## Schema drift in a new ClinVar release

Symptoms: staging fails with a polars error about columns or "more fields
than defined"; or the load fails on the `review_status` foreign key; or
`vwh validate` reports a check the previous month passed.

- New or renamed column: compare the header with the previous release,
  `gzip -dc variant_summary_YYYY-MM.txt.gz | head -1 | tr '\t' '\n'`.
  Staging selects columns by name, so added columns are ignored and renamed
  ones fail loudly. Update `sources/clinvar.py`, add a fixture row with the
  new layout, and release a new version.
- New review status text: the foreign key to `review_status` rejects it.
  Add it with its star level in a new migration (never edit `0002`),
  citing https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/.
- New classification wording: it lands in class `Other`. Check
  `SELECT clinical_significance, count(*) FROM classification WHERE is_current
  AND clinsig_class = 'Other' GROUP BY 1 ORDER BY 2 DESC` against the last
  month and extend `CLASS_EXACT` if a new wording means P/LP, B/LB or VUS.

## Slow queries

Get the plan first: `EXPLAIN ANALYZE <query>` on either engine. On DuckDB,
look for a full scan where a filter on position should prune; sorting the
table or Parquet export by `chrom, pos` cut the BRCA1 region count from 6.6
to 1.5 ms (`docs/performance.md`). On PostgreSQL, a sequential scan with a
large "Rows Removed by Filter" calls for an index; a B-tree cannot hold
`variant_key` values over 2,704 bytes, so use a hash index for equality on
that column. Aggregates over every row (top genes by P/LP) do not improve
with indexes; precompute them per release if they become a problem.

## Disk

The 2026-10 build used 1.60 GB of raw files, a 3.7 GB DuckDB file and the
staging Parquet. A DuckDB file grows during a load and the WAL is
checkpointed at commit; keep free space of at least twice the database size
before a refresh. `du -sh $VWH_DATA_DIR/*` shows where it went. Staging
Parquet for old releases can be deleted once the release is loaded; the raw
files and the manifest are the record and should be kept.
