# SOP: monthly ClinVar refresh

ClinVar publishes a monthly release in
`ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/` early in the
month (2026-10 files are dated 2026-10-01). The steps below add one release.
Run them as the loader account; analysts keep reading the previous release
until step 5 commits.

1. Add the release to `config/config.yaml`, for example
   `releases: ["2025-10", "2026-10", "2026-11"]`. Releases load oldest first;
   the loader refuses a release older than one already loaded.
2. Fetch: `vwh --log-file refresh.jsonl fetch clinvar --release 2026-11`.
   Check that the log shows two `fetched` lines with sizes and SHA-256
   values. A size that differs from the server's stops the fetch.
3. Stage: `vwh stage clinvar --release 2026-11`. The log reports rows and
   `repeated_scv_rows_dropped`; 2026-10 dropped 6. A jump in that number
   or a parse error means the file layout changed: stop and read
   `docs/operations/runbook.md`, section "Schema drift".
4. Back up the database. DuckDB: copy `db/warehouse.duckdb`. PostgreSQL:
   `pg_dump -Fc`.
5. Load: `vwh --log-file refresh.jsonl load clinvar --release 2026-11`
   (add `--dsn` for PostgreSQL). The release is one transaction; a failure
   leaves the previous release in place and logs `load failed`.
6. Validate: `vwh validate --report reports/validation_2026-11.md`. Every
   check must pass. Compare the row counts with the previous month; the
   2025-10 to 2026-10 change was +866,997 variations, so a month should be a
   fraction of that.
7. Spot-check: `vwh query 03` lists class changes since the previous
   release. Look at the P/LP to B/LB and B/LB to P/LP rows (20 and 8 between
   2025-10 and 2026-10); those are the ones a lab will ask about.
8. If anything is wrong after commit, `vwh unload clinvar` removes the
   latest release in one transaction and marks it `rolled_back`.
9. Record the release, the validation report and any deviations in the
   CHANGELOG under "Data".
