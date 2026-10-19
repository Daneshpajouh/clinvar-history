# What this database is for, without the jargon

Everyone carries small differences in their DNA, called variants. When a
genetic test finds a variant in a gene linked to cancer, such as BRCA1, the
lab has to say whether it is likely to cause disease ("pathogenic"), likely
harmless ("benign"), or not yet known ("uncertain significance").

Labs share these judgements in ClinVar, a public database run by the US
National Center for Biotechnology Information. ClinVar keeps every lab's
judgement and a combined summary per variant, and the summary changes as
evidence arrives. Between October 2025 and October 2026, 1,415 variants
moved from "uncertain" to "pathogenic or likely pathogenic", and 20,364 moved
from "uncertain" to "conflicting" because labs disagreed.

Two other public sources help judge a variant:

- gnomAD counts how often each variant appears in hundreds of thousands of
  people, grouped by genetic ancestry. A variant that is common in some
  group is unlikely to cause a rare, severe disease.
- MaveDB holds results from laboratory experiments that test thousands of
  variants of one gene at once and score how well the protein still works.

This project puts all three in one database and keeps every ClinVar
release, so a question like "what did ClinVar say about this variant last
October, and do the population counts and the lab experiments agree?" is one
query. For the seven genes with MaveDB data, the experiments separate
pathogenic from benign variants well: in the BRCA1 score set
urn:mavedb:00000097-0-2, a randomly chosen pathogenic variant scores lower
than a randomly chosen benign one 99.1% of the time (`docs/results.md`,
query 06, with the figure for each score set).

The database refuses to half-load a release: either the whole month goes in
or nothing changes. Every row can be traced to the file it came from and
that file's fingerprint (SHA-256).
