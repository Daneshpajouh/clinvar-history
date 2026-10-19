# Roadmap

1. Load the full warehouse into PostgreSQL. As an operator, I can run
   `clinvar-history load --dsn ...` on the 2025-10 and 2026-10 releases. Done when the
   load completes, `clinvar-history validate --dsn` passes, and `variant_key` no longer
   relies on a B-tree that rejects keys over 2,704 bytes (plan: a
   generated `md5(variant_key)` unique column, with a hash index on the
   key for lookups), measured in `docs/performance.md`.
2. Snakemake workflow for the monthly refresh. As an operator, I add a
   release to the config and run one command. Done when the workflow
   chains fetch, stage, load, validate and report with per-rule logs and
   `benchmark:` files, passes `snakemake --lint` and `snakefmt --check`,
   and a dry run on the next ClinVar release lists only the new jobs.
3. Drift alerts. As a curator, I see when a ClinVar month changes shape.
   Done when `clinvar-history validate` compares this month's counts (repeated SCVs,
   orphan submissions, class `Other`) with the previous month and fails
   above a configured ratio.
4. HPRC and ENCODE context. As an analyst, I can see whether a panel
   variant occurs in HPRC release 1.1 haplotypes and which ENCODE
   experiments target the gene. Done when both load with provenance and
   each has a cookbook query with fixture tests.
5. Indels in GraphKB-style notation. Done when deletions, insertions and
   delins are shifted to the 3' position HGVS requires, checked against
   the GRCh38 sequence, with tests on repeats.
