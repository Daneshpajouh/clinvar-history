# Postmortem: four failures while building the first two-release ClinVar load

- Date: 2026-10-19, between 11:01 and 11:56 Pacific
- Author: Amir Daneshpajouh
- Status: reviewed by the author; no production users were affected

These happened while building v1.0.0 against real ClinVar files. Each one
changed the code or the schema, so they are recorded here with the evidence.

## 1. A download script logged success for a failed transfer

The first ClinVar fetch was a shell loop. Two FTP connections timed out:

```
curl: (8) Failed to connect to ftp.ncbi.nlm.nih.gov port 21 after 75861 ms: Couldn't connect to server
2026-10-19 11:02:43 PDT done variant_summary_2026-10.txt.gz exit=0 size=
```

The log said `exit=0` because `$?` was read after a `$(date ...)` command
substitution in the same `echo`, so it held the exit status of `date`. The
empty `size=` was the only sign. A later retry also hit
`curl: (18) transfer closed with 62068409 bytes remaining to read` and recovered
through `--retry`.

Fix: `vwh.fetch.curl` reads the return code first, writes to a `.part` file,
renames only on success, and `fetch_clinvar` compares the local size with the
server's reported size and tests the whole gzip stream before recording the
file. All four files matched the FTP sizes (450,727,547; 394,172,714;
384,432,958; 336,409,343 bytes).

## 2. The same SCV appears twice in one release

The first load of 2026-10 failed on the submission primary key:

```
ConstraintException: PRIMARY KEY or UNIQUE constraint violation: duplicate key "1, SCV000058352"
```

Four SCV accessions in `submission_summary_2026-10.txt.gz` are listed more than once
under the same VariationID with different classifications. SCV000058352 from
OMIM appears as both "not provided" and "Pathogenic". Staging now keeps the
first row in file order and logs the number dropped (6 rows in 2026-10, 8 in
2025-10 counted by `repeated_scv_rows_dropped`).

## 3. An AlleleID moved to a new VariationID

```
ConstraintException: Duplicate key "allele_id: 3396438"
```

`clinvar_variation.allele_id` had a UNIQUE constraint across all releases.
Between 2025-10 and 2026-10, 65 AlleleIDs moved to a new VariationID (for
example VariationID 309920 became 4917283 for the MYO1A allele). The
constraint was dropped; `vwh validate` now checks AlleleID uniqueness among
current variations only.

## 4. DuckDB foreign keys and a five-minute upsert

With foreign keys from `classification` and `submission` to
`clinvar_variation`, the second release failed:

```
Violates foreign key constraint because key "variation_id: 1369313" is still referenced by a foreign key in a different table
```

DuckDB 1.5.6 runs `INSERT ... ON CONFLICT DO UPDATE` on a referenced parent
row as a delete and insert, which the foreign key check rejects. The two
constraints moved to `migrations/0004_foreign_keys.postgres.sql` and
`vwh validate` checks them on DuckDB.

With the constraints gone the upsert succeeded but took 295.24 s for the
`clinvar_variation` step (4,575,785 staged rows against 3,708,788 existing,
log `logs/load_2026-10_before.jsonl`). Only 4,212 existing rows had changed
attributes. The step now updates the changed rows and inserts the new ones,
and took 2.69 s in the next full load. The `last_release_id` column, which
forced a write to every row, was removed; presence in a release is read from
`classification`. Details and plans are in `docs/performance.md`.

## Follow-up actions

| Action | Done when |
| --- | --- |
| Alert when `repeated_scv_rows_dropped` grows month to month | ROADMAP milestone 3 |
| Test the PostgreSQL path on the full data, not only fixtures | ROADMAP milestone 1 |
