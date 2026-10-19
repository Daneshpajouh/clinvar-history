# Data sources

Every file below was fetched by `vwh fetch` on 2026-10-19 and is recorded in `<data_dir>/raw/manifest.jsonl` and, after loading, in the `provenance` table. Raw data stays outside the repository; `tests/data` holds only the hand-written fixtures.

31 files, 1,595.7 MB in total.

## Terms

- ClinVar: NCBI places no restrictions on use or distribution of the data (https://www.ncbi.nlm.nih.gov/home/about/policies/). The HTTPS host's robots.txt disallows all crawlers, so the four named files were fetched over NCBI's FTP service, which NCBI provides for bulk downloads; nothing was crawled.
- gnomAD v4.1: terms of use at https://gnomad.broadinstitute.org/terms, as linked from the AWS Open Data registry entry. The page renders client-side and was not read by script. Only ten gene regions were read, by remote tabix index, keeping 45 INFO fields.
- MaveDB: each score set carries its own licence; all eight used here are CC0 (from the API record, stored in `score_set.licence`).
- Ensembl REST: gene coordinates only; terms at https://www.ensembl.org/info/about/legal/ (that host returned HTTP 403 to curl, so the text was not read by script).

## Files

| Source | Release | File | Bytes | SHA-256 | Fetched |
| --- | --- | --- | ---: | --- | --- |
| clinvar | 2025-10 | `clinvar/submission_summary_2025-10.txt.gz` | 336,409,343 | `9d55341fded9c9077f0f06532d4106f625816f1b2972f0ffbf0441f7657d0e40` | 2026-10-19 11:17 |
| clinvar | 2026-10 | `clinvar/submission_summary_2026-10.txt.gz` | 394,172,714 | `c93758c972fbeb958b49aa560a374bdaf5c57cc4f159644a19bed88200a870ac` | 2026-10-19 11:17 |
| clinvar | 2025-10 | `clinvar/variant_summary_2025-10.txt.gz` | 384,432,958 | `b99920190c2eb00382cf9ec154442bb83fe5a14a397f93e6db22c8fda094fc77` | 2026-10-19 11:17 |
| clinvar | 2026-10 | `clinvar/variant_summary_2026-10.txt.gz` | 450,727,547 | `a6a58df4d9049c9187a79a8fb4e70f1f3b5550e1708c6c74b7be0b268f5032da` | 2026-10-19 11:17 |
| ensembl | GRCh38 | `ensembl/genes.json` | 1,604 | `07986d4156f496984c0b0e173176259e4a51850824d6d7aa2ac9ae93c6378eb3` | 2026-10-19 11:16 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.BRCA1.vcf.gz` | 2,857,252 | `868c47d331f14cb96ad83414367a65ae9e1e53e54501dd8b897f8065af68c9ae` | 2026-10-19 11:19 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.BRCA2.vcf.gz` | 1,810,517 | `027cfc38ed5f8d4c24d689f2f3ebe93c21a2f846bb82b55090a8746b7a1fbe86` | 2026-10-19 11:19 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.CHEK2.vcf.gz` | 1,278,438 | `2e256a08505de085b2504caceea6f6ab82e9a05f84a3d0ef3bc4805ea2a7a5c0` | 2026-10-19 11:20 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.MLH1.vcf.gz` | 1,205,591 | `9ce790edcc5e424e8af867dd2bf37a45c628bd4cb2cb8ba5d118b06cd275a77a` | 2026-10-19 11:19 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.MSH2.vcf.gz` | 5,260,479 | `a25f3bb048dbe4fb1db56858b6139eabc701838a98ad3ef2d847de4134559e1a` | 2026-10-19 11:19 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.MSH6.vcf.gz` | 2,819,859 | `780f0aae5699cb40d2a26e80ba3e6d948c1940b85547440bf618d773b0348cc5` | 2026-10-19 11:19 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.PALB2.vcf.gz` | 874,154 | `1badac0a156bfa559ebb6d821e1210f553b1f0bd553fa92782ec9d8cbe8f8dc0` | 2026-10-19 11:19 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.PMS2.vcf.gz` | 1,060,574 | `db23cb54d84d0f3e165c7005f955b7e62403bcd47c8780879aaa910df6256285` | 2026-10-19 11:19 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.PTEN.vcf.gz` | 1,834,929 | `a6904d71b5dc5f4d9b28757e89891ff687433cf03895e8ecc78f79d435c328c6` | 2026-10-19 11:19 |
| gnomad | 4.1 | `gnomad/gnomad.joint.v4.1.TP53.vcf.gz` | 777,481 | `5dba5a4bd5c2cfb647b0ac1486c4a8486b6d7a389d232c1407d7ab878eff69e0` | 2026-10-19 11:19 |
| mavedb | urn:mavedb:00000013-a-1 | `mavedb/00000013-a-1.json` | 57,369 | `266cfddaa11c0a7457f28c86d66d81cbe9041128c5ecb97f97a044b7c605d728` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00000013-a-1 | `mavedb/00000013-a-1.scores.csv` | 1,735,960 | `ceaf3f0720af8aa06012d60959efbcd7ab54a5317d2bebdace8a0f49de4b2b97` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00000050-a-1 | `mavedb/00000050-a-1.json` | 71,799 | `ed26cacd32caf1358b5e69e76cd0cbde94fd6647f21a8ef3ab19b0e1c2c6cde4` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00000050-a-1 | `mavedb/00000050-a-1.scores.csv` | 1,394,308 | `83b2a4a6692b32b7f14b89589eb858ceb5aae2e5941065b387be058adca2e1b9` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00000054-a-1 | `mavedb/00000054-a-1.json` | 54,312 | `90cde5883d76f85b644888bed23056e068ae44c55012270e6b5770beea86a4fb` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00000054-a-1 | `mavedb/00000054-a-1.scores.csv` | 2,438,297 | `16764c9b4afed9f7507bb8e615fdcd703329f3145108a8c28bdf0b1c60f076e7` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00000068-0-1 | `mavedb/00000068-0-1.json` | 45,729 | `1efbc51c0fa9f4d79290fcd0d3b46761da9c0872d485f854a4cba9e420751089` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00000068-0-1 | `mavedb/00000068-0-1.scores.csv` | 552,441 | `774a2c52afd687eaff6f41e47e8f673dc9811b4cc973f831afb51aa97d7baca6` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00000097-0-2 | `mavedb/00000097-0-2.json` | 76,971 | `f37f8a3cb8322c12b61b54319bae421c6e574109412eca9c6b9a86fef3db9933` | 2026-10-19 11:17 |
| mavedb | urn:mavedb:00000097-0-2 | `mavedb/00000097-0-2.scores.csv` | 610,024 | `906dc152f28b4c8261e4e532a03c9c42f2e45e211aa3ada12e3c826c151580ec` | 2026-10-19 11:17 |
| mavedb | urn:mavedb:00001205-a-1 | `mavedb/00001205-a-1.json` | 37,668 | `03dc49029b35b5374df04cd67e753f0c113f08ea0413d83679c3c75cae137aa5` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00001205-a-1 | `mavedb/00001205-a-1.scores.csv` | 905,423 | `3589cba8ca1ad173f40cd73fd9a733ad57c607f2de9009f539e73f560d0292f6` | 2026-10-19 11:18 |
| mavedb | urn:mavedb:00001259-a-2 | `mavedb/00001259-a-2.json` | 7,853 | `6b46d6e78933a511dc66054ae904bd65f352cfb653430de61e23055e2093c746` | 2026-10-19 11:17 |
| mavedb | urn:mavedb:00001259-a-2 | `mavedb/00001259-a-2.scores.csv` | 1,633,971 | `62a634dfa201283faaf223d8e33e373a528a62aa88d6aa8d5742992b12b34cdb` | 2026-10-19 11:17 |
| mavedb | urn:mavedb:00001279-a-1 | `mavedb/00001279-a-1.json` | 15,841 | `627b7a21bce107c54537c8257ffe5c3c86bcbb19cedd7a38b3325c139ee4bfeb` | 2026-10-19 11:17 |
| mavedb | urn:mavedb:00001279-a-1 | `mavedb/00001279-a-1.scores.csv` | 489,662 | `4e1798c8cd5564221faeb247c5fa2102a147c13fa246b5fc1349e9873135e6d8` | 2026-10-19 11:17 |

## URLs

- ClinVar: `ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/archive/{variant,submission}_summary_{2025-10,2026-10}.txt.gz`
- gnomAD: `https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/vcf/joint/gnomad.joint.v4.1.sites.chr{N}.vcf.bgz`, regions from `raw/ensembl/regions.bed`
- MaveDB: `https://api.mavedb.org/api/v1/score-sets/{urn}` and `.../{urn}/scores`
- Ensembl: `https://rest.ensembl.org/lookup/symbol/homo_sapiens/{symbol}`
