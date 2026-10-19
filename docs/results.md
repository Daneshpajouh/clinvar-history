# Results on the full build

Cookbook output on the DuckDB warehouse built on 2026-10-19 at 12:46 PT with
version 1.0.1 (ClinVar 2025-10 and 2026-10, gnomAD v4.1 joint for ten genes,
eight MaveDB score sets for seven genes). Produced with
`vwh --log-level WARNING query NN --format csv` for NN in 01 to 07. Query 08,
a list of every P/LP single nucleotide variant in the panel, is left out.

## 01. Conflicting aggregate records by gene (top 15)

| gene_symbol | conflicting | variants | pct_conflicting | conflict_rank |
| --- | --- | --- | --- | --- |
| BRCA2 | 5744 | 21701 | 26.47 | 1 |
| TTN | 4454 | 40271 | 11.06 | 2 |
| BRCA1 | 2924 | 15559 | 18.79 | 3 |
| TSC2 | 1613 | 12554 | 12.85 | 4 |
| ATM | 1524 | 19490 | 7.82 | 5 |
| MSH2 | 1431 | 8225 | 17.4 | 6 |
| NF1 | 1356 | 17414 | 7.79 | 7 |
| MSH6 | 1242 | 10512 | 11.82 | 8 |
| NEB | 1015 | 12606 | 8.05 | 9 |
| POLE | 990 | 11210 | 8.83 | 10 |
| ADGRV1 | 880 | 7475 | 11.77 | 11 |
| APOB | 851 | 5265 | 16.16 | 12 |
| DNAH11 | 798 | 6715 | 11.88 | 13 |
| APC | 790 | 17038 | 4.64 | 14 |
| DSP | 772 | 6218 | 12.42 | 15 |

## 02. Review stars of current aggregate records

| stars | variants | pct | cum_pct_at_or_above |
| --- | --- | --- | --- |
| 4 | 54 | 0.0 | 0.0 |
| 3 | 22319 | 0.49 | 0.49 |
| 2 | 740832 | 16.19 | 16.68 |
| 1 | 3448583 | 75.37 | 92.05 |
| 0 | 363997 | 7.95 | 100.0 |

## 03. Class changes between 2025-10 and 2026-10

| from_class | to_class | variations |
| --- | --- | --- |
| VUS | Conflicting | 20364 |
| B/LB | Conflicting | 7618 |
| P/LP | Conflicting | 3262 |
| Conflicting | B/LB | 2693 |
| VUS | B/LB | 2182 |
| VUS | P/LP | 1415 |
| Conflicting | P/LP | 1257 |
| P/LP | VUS | 615 |
| Conflicting | VUS | 585 |
| B/LB | VUS | 484 |
| Other | P/LP | 453 |
| Other | VUS | 236 |
| Other | B/LB | 92 |
| P/LP | Other | 83 |
| VUS | Other | 44 |
| Other | Conflicting | 26 |
| P/LP | B/LB | 20 |
| B/LB | P/LP | 8 |
| B/LB | Other | 7 |
| Conflicting | Other | 3 |

## 04. Panel P/LP variants in gnomAD v4.1 by ancestry group (PASS sites, AN >= 1000)

| ancestry_group | plp_variants | observed | rare | af_at_least_0_001 |
| --- | --- | --- | --- | --- |
| afr | 21939 | 226 | 225 | 1 |
| all | 21939 | 2084 | 2083 | 1 |
| amr | 21939 | 158 | 157 | 1 |
| asj | 21939 | 52 | 49 | 3 |
| eas | 21939 | 164 | 164 | 0 |
| fin | 21939 | 77 | 76 | 1 |
| mid | 21939 | 36 | 36 | 0 |
| nfe | 21939 | 1485 | 1484 | 1 |
| remaining | 21939 | 236 | 236 | 0 |
| sas | 21939 | 277 | 276 | 1 |

## 05. Panel P/LP variants with AF >= 0.001 in a group

| gene_symbol | variant_key | name | stars | peak_group | peak_af | ac | an |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRCA2 | 13-32340300-GT-G | NM_000059.4(BRCA2):c.5946del (p.Ser1982fs) | 3 | asj | 0.005339 | 158 | 29596 |
| BRCA1 | 17-43124027-ACT-A | NM_007294.4(BRCA1):c.68_69del (p.Glu23fs) | 3 | asj | 0.004158 | 123 | 29578 |
| MSH2 | 2-47414421-A-T | NM_000251.3(MSH2):c.942+3A>T | 3 | nfe | 0.003409 | 24 | 7040 |
| PALB2 | 16-23634953-CA-C | NM_024675.4(PALB2):c.1592del (p.Leu531fs) | 3 | fin | 0.00175 | 112 | 64008 |
| CHEK2 | 22-28711994-A-G | NM_007194.4(CHEK2):c.707T>C (p.Leu236Pro) | 2 | amr | 0.001734 | 104 | 59990 |
| BRCA1 | 17-43057062-T-TG | NM_007294.4(BRCA1):c.5266dup (p.Gln1756fs) | 3 | asj | 0.001183 | 35 | 29592 |
| CHEK2 | 22-28734664-G-A | NM_007194.4(CHEK2):c.58C>T (p.Gln20Ter) | 2 | sas | 0.001109 | 101 | 91068 |

CHEK2 c.1100del (22-28695868-AG-A, AF 0.0086 in Finnish samples) is not listed because its joint gnomAD record has FILTER `EXOMES_FILTERED`; of the 385,744 gnomAD sites loaded, 259,545 are PASS.

## 06. MaveDB scores against ClinVar classes, per score set

| gene_symbol | urn | match_level | n_plp | n_blb | median_plp | median_blb | auc_plp_lower |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRCA1 | urn:mavedb:00000097-0-2 | nucleotide | 460 | 603 | -2.059 | -0.045 | 0.991 |
| BRCA2 | urn:mavedb:00001279-a-1 | nucleotide | 449 | 1446 | -1.365 | 0.213 | 0.99 |
| CHEK2 | urn:mavedb:00001205-a-1 | protein | 133 | 374 | 0.303 | 1.007 | 0.9 |
| MSH2 | urn:mavedb:00000050-a-1 | protein | 140 | 289 | 2.348 | -3.731 | 0.057 |
| PALB2 | urn:mavedb:00001259-a-2 | nucleotide | 344 | 1184 | -0.143 | 0.004 | 0.996 |
| PTEN | urn:mavedb:00000013-a-1 | protein | 198 | 127 | 0.352 | 0.987 | 0.857 |
| PTEN | urn:mavedb:00000054-a-1 | protein | 362 | 9 | -2.931 | 0.091 | 0.969 |
| TP53 | urn:mavedb:00000068-0-1 | protein | 305 | 461 | 0.88 | -0.217 | 0.038 |

`auc_plp_lower` is the probability that a P/LP variant scores lower than a B/LB variant. BRCA1 (0.991), BRCA2 (0.990), PALB2 (0.996), PTEN (0.969 and 0.857) and CHEK2 (0.900) score loss of function low; TP53 (0.038) and MSH2 (0.057) score it high, so values near 0 there mean equally strong separation.

## 07. Top three submitters per panel gene, 2026-10

| gene_symbol | submitter_rank | submitter | submissions |
| --- | --- | --- | --- |
| BRCA1 | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 7837 |
| BRCA1 | 2 | Ambry Genetics | 6521 |
| BRCA1 | 3 | Evidence-based Network for the Interpretation of Germline Mutant Alleles (ENIGMA) | 3329 |
| BRCA2 | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 13608 |
| BRCA2 | 2 | Ambry Genetics | 12469 |
| BRCA2 | 3 | Color Diagnostics, LLC DBA Color Health | 5397 |
| CHEK2 | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 3284 |
| CHEK2 | 2 | Ambry Genetics | 2428 |
| CHEK2 | 3 | Myriad Genetics, Inc. | 1100 |
| MLH1 | 1 | Ambry Genetics | 3570 |
| MLH1 | 2 | Labcorp Genetics (formerly Invitae), Labcorp | 3557 |
| MLH1 | 3 | Myriad Genetics, Inc. | 1775 |
| MSH2 | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 4932 |
| MSH2 | 2 | Ambry Genetics | 4900 |
| MSH2 | 3 | Myriad Genetics, Inc. | 2162 |
| MSH6 | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 6866 |
| MSH6 | 2 | Ambry Genetics | 6708 |
| MSH6 | 3 | Color Diagnostics, LLC DBA Color Health | 2806 |
| PALB2 | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 4578 |
| PALB2 | 2 | Ambry Genetics | 3892 |
| PALB2 | 3 | Myriad Genetics, Inc. | 1934 |
| PMS2 | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 3927 |
| PMS2 | 2 | Ambry Genetics | 3801 |
| PMS2 | 3 | Color Diagnostics, LLC DBA Color Health | 1571 |
| PTEN | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 1820 |
| PTEN | 2 | Ambry Genetics | 1556 |
| PTEN | 3 | GeneDx | 911 |
| TP53 | 1 | Labcorp Genetics (formerly Invitae), Labcorp | 2454 |
| TP53 | 2 | Ambry Genetics | 1863 |
| TP53 | 3 | Genome-Nilou Lab | 1266 |
