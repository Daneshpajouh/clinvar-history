-- Current pathogenic or likely pathogenic panel variants and their gnomAD
-- joint frequency in each genetic ancestry group, from the latest loaded
-- gnomAD release. The join is an exact match on the GRCh38 key
-- chrom-pos-ref-alt; ClinVar and gnomAD both publish left-aligned VCF alleles
-- on GRCh38, so no liftover or normalisation step sits between them.
-- Only gnomAD sites with FILTER = PASS count, and a group needs AN >= 1000
-- (500 people) before its frequency is used. "rare" means 0 < AF < 0.001.
WITH gnomad_latest AS (
    SELECT release_id
    FROM source_release
    WHERE source = 'gnomad' AND status = 'loaded'
    ORDER BY label DESC
    LIMIT 1
),

plp AS (
    SELECT variant_key
    FROM v_variant_current
    WHERE in_panel AND clinsig_class = 'P/LP' AND variant_key IS NOT NULL
),

freq AS (
    SELECT
        pf.variant_key,
        pf.ancestry_group,
        pf.ac,
        pf.af
    FROM population_frequency AS pf
    INNER JOIN gnomad_latest AS g ON pf.release_id = g.release_id
    WHERE pf.filter = 'PASS' AND pf.an >= 1000
)

SELECT
    f.ancestry_group,
    (SELECT count(*) FROM plp) AS plp_variants,
    sum(CASE WHEN f.ac > 0 THEN 1 ELSE 0 END) AS observed,
    sum(CASE WHEN f.ac > 0 AND f.af < 0.001 THEN 1 ELSE 0 END) AS rare,
    sum(CASE WHEN f.af >= 0.001 THEN 1 ELSE 0 END) AS af_at_least_0_001
FROM plp AS p
INNER JOIN freq AS f ON p.variant_key = f.variant_key
GROUP BY f.ancestry_group
ORDER BY f.ancestry_group;
