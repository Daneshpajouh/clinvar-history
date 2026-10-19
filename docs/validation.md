# Validation report

Output of `vwh validate --report` on the full DuckDB build of 2026-10-19 (ClinVar 2025-10 and 2026-10, gnomAD v4.1 for ten genes, eight MaveDB score sets for seven genes). Each check is a SQL count of violating rows in `src/vwh/validate.py`; the row-count checks compare the rows staged from each file with the rows loaded.

| Check (duckdb) | Result | Detail |
| --- | --- | --- |
| variant key matches chrom-pos-ref-alt | pass | 0 violating rows |
| alleles use only A, C, G, T, N | pass | 0 violating rows |
| one current classification per variation | pass | 0 violating rows |
| classification versions do not overlap | pass | 0 violating rows |
| classification rows reference a ClinVar variation | pass | 0 violating rows |
| submission rows reference a ClinVar variation | pass | 0 violating rows |
| every ClinVar variation has a classification history | pass | 0 violating rows |
| AlleleID unique among current variations | pass | 0 violating rows |
| gnomAD AF agrees with AC/AN (abs diff < 1e-4) | pass | 0 violating rows |
| gnomAD rows reference a known variant | pass | 0 violating rows |
| score sets carry a licence | pass | 0 violating rows |
| functional scores reference a score set | pass | 0 violating rows |
| provenance SHA-256 values are 64 hex characters | pass | 0 violating rows |
| releases left in 'loading' state | pass | 0 violating rows |
| row counts clinvar 2025-10 submission_summary_2025-10.txt.gz | pass | staged 5662226, loaded 5596011; 66215 rows name a VariationID absent from variant_summary |
| row counts clinvar 2025-10 variant_summary_2025-10.txt.gz | pass | staged 3708788, loaded 3708788 |
| row counts clinvar 2026-10 submission_summary_2026-10.txt.gz | pass | staged 6735012, loaded 6661309; 73703 rows name a VariationID absent from variant_summary |
| row counts clinvar 2026-10 variant_summary_2026-10.txt.gz | pass | staged 4575785, loaded 4575785 |

Submission rows that name a VariationID absent from variant_summary (66,215 in 2025-10, 73,703 in 2026-10) are dropped at load, by design: the aggregate file is the source of variations. Their count is kept in `provenance.rows_staged` and `rows_loaded`.
