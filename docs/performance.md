# Performance

All numbers are from runs on 2026-10-19 on one machine: Apple M3 Ultra,
28 logical CPUs, 96 GB RAM, macOS 27.0.1, Python 3.13.9, DuckDB 1.5.6 limited
to 6 threads, SQLite 3.50.4 (the build Python links), PostgreSQL 17.6 in Docker
(`shared_buffers=2GB`, `work_mem=256MB`). Raw results:
`bench/results/bench_2026-10-19.csv`; plans: `bench/plans/`.

## Load: rewriting a 295-second upsert

The second ClinVar release first loaded `clinvar_variation` with
`INSERT ... ON CONFLICT (variation_id) DO UPDATE` over all 4,575,785 staged
rows, 3,708,788 of which already existed. That step took 295.24 s
(`step done` log line, `clinvar_variation`, 2026-10-19 11:51 to 11:56).
Only 4,212 existing rows had a changed attribute; the rest were rewritten to
bump a `last_release_id` column.

The loader now runs an `UPDATE ... FROM` restricted to rows where any
attribute `IS DISTINCT FROM` the staged value, then an `INSERT ... WHERE NOT
EXISTS` for new VariationIDs, and `last_release_id` is gone (presence in a
release is read from `classification`). Same data, same machine:

| Step | Before | After |
| --- | ---: | ---: |
| `clinvar_variation`, 2026-10 on top of 2025-10 | 295.24 s | 2.69 s |
| whole `vwh load all` (both releases, gnomAD, MaveDB) | not completed | 115.05 s wall, 6.9 GB peak |

An isolated rerun of the two new statements on a copy of the 2025-10
database took 0.92 s (update) and 2.38 s (insert),
`bench/results/upsert_rewrite_after.txt`.

## Queries on 4,555,177 current ClinVar records

`vwh bench` exports the current records that have a GRCh38 key to three
files and loads the same rows into SQLite and PostgreSQL. Each case runs
once to warm up, then 5 timed runs; the table shows the median.

| Engine | Layout | Point lookup | BRCA1 region count | Top 10 genes by P/LP |
| --- | --- | ---: | ---: | ---: |
| DuckDB | CSV, gzip (74.9 MB) | 673.0 ms | 708.0 ms | 655.2 ms |
| DuckDB | Parquet, VariationID order (111.6 MB) | 19.7 ms | 6.6 ms | 8.1 ms |
| DuckDB | Parquet, sorted by chrom, pos (87.0 MB) | 3.9 ms | 1.5 ms | 6.9 ms |
| SQLite | no index | 232.2 ms | 233.4 ms | 318.1 ms |
| SQLite | B-tree on key and (chrom, pos) | 0.01 ms | 14.3 ms | 384.5 ms |
| PostgreSQL | no index | 57.8 ms | 65.9 ms | 101.5 ms |
| PostgreSQL | hash on key, B-tree on (chrom, pos) | 0.48 ms | 6.1 ms | 100.4 ms |

What the numbers say:

- Every DuckDB query over gzip CSV costs a full decompress and parse, about
  0.67 s. Parquet removes that.
- Sorting by position helps range and point queries because DuckDB skips
  Parquet row groups using their min/max statistics. Both files have 38 row
  groups; by those statistics all 38 can hold BRCA1 rows in the
  VariationID-ordered file and 3 in the sorted one. The sorted file is also
  22% smaller because neighbouring rows compress together. Both plans
  (`duckdb_region_count_parquet_*.txt`) push the filter into the scan and
  return 15,336 rows; the difference is in how many row groups are read
  (7.8 ms against 1.8 ms total time in the plans).
- Indexes matter for the row stores and not for the aggregate. In
  PostgreSQL the region count moved from a parallel sequential scan that
  discarded 1,513,280 rows per worker (65.9 ms) to a bitmap index scan on
  `(chrom, pos)` that touched 3,753 buffers (6.1 ms). The top-10 aggregate
  reads every row either way.

## A B-tree limit found by the benchmark

The first benchmark run failed creating a B-tree on `variant_key` in
PostgreSQL:

```
index row size 2880 exceeds btree version 4 maximum 2704 for index "bench_cur_key"
```

Some ClinVar alleles are kilobases long, and the key carries both alleles.
The benchmark uses a hash index, which stores a 4-byte hash and serves
equality lookups (0.48 ms). The warehouse's primary key on
`variant.variant_key` is a B-tree on the same values, so a full PostgreSQL
load is expected to fail the same way; that load has not been run.
`ROADMAP.md` milestone 1 covers it.
