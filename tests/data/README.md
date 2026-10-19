# Test fixtures

Hand-written files in the real formats. Gene GENEX, the laboratories LabA to
LabD and every number here are invented; coordinates for BRCA1 and TP53 are
real GRCh38 positions so the panel join works. `conftest.py` gzips the
ClinVar and gnomAD files into a temporary data directory and records them
in a manifest, as `clinvar-history fetch` would.

`variant_summary_2025-10.tsv`, `variant_summary_2026-10.tsv` (43 columns,
one GRCh37 and one GRCh38 row per variant; staging keeps GRCh38):

| Variant | Gene | 2025-10 | 2026-10 | Why it is here |
| --- | --- | --- | --- | --- |
| V1 1001 | BRCA1 | Uncertain significance | Likely pathogenic | reclassification VUS to P/LP |
| V2 1002 | BRCA1 | Pathogenic, expert panel | same | unchanged, 3 stars |
| V3 1003 | TP53 | Pathogenic | same, Name cites NM_000546.7 | matched by gnomAD and MaveDB; the transcript change is an overwritten attribute that unload must restore |
| V4 1004 | TP53 | Benign | Likely benign | new SCD version, same class |
| V5 1005 | GENEX | Conflicting | same | conflicting aggregate record |
| V6 1006 | GENEX | Likely benign | absent | variant removed from ClinVar |
| V7 1007 | BRCA1 | Benign, no criteria | same | 0 stars, excluded from concordance |
| V8 1008 | TP53 | absent | Likely pathogenic | variant added |
| V9 1009 | TP53 | absent | Benign | synonymous change (p.Arg174=) |
| V10 1010 | GENEX | absent | Pathogenic | copy number loss: no VCF alleles, PositionVCF -1, LastEvaluated "sometime in 2024" |

`submission_summary_2025-10.tsv`, `submission_summary_2026-10.tsv`: the
`##` and `#VariationID:` comment lines of the real file, then SCV rows.
2026-10 holds SCV0000011 twice for V7 ("Benign" then "not provided"; the
first is kept) and SCV0000014 for VariationID 5555, which is not in
variant_summary (dropped at load).

`gnomad.joint.v4.1.FIXTURE.vcf`: joint AC, AN, AF and nhomalt for `all`,
`afr` and `nfe` at V1 (AF 0.002 in afr, rare elsewhere), V3 (absent in afr),
V4 (AF 0.3, a common benign variant) and V2 with FILTER `EXOMES_FILTERED`
(AF 0.01 in afr), which queries 04 and 05 must ignore.

`00000097-0-2.*` (BRCA1, nucleotide matching): scores for V1, V2, V7 and one
change with no ClinVar record. `00000068-0-1.*` (TP53, protein matching):
p.Arg175His, p.Arg175Cys, p.Pro72Arg, p.Arg174=, p.Met1Ala with no ClinVar
match, row 6 with no HGVS at all, and row 7 repeating p.Arg175His with a
second score (-2.0 after -3.0; query 06 uses the mean, -2.5).

`genes.json`: Ensembl GRCh38 coordinates for BRCA1 and TP53, the two panel
genes in the fixtures.
