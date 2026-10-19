-- Current pathogenic or likely pathogenic panel variants and their gnomAD v4.1
-- joint frequency in each genetic ancestry group. The join is an exact match
-- on the GRCh38 key chrom-pos-ref-alt; both ClinVar and gnomAD publish
-- left-aligned VCF alleles on GRCh38, so no liftover or normalisation step
-- sits between them. "rare" means 0 < AF < 0.001.
WITH plp AS (
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
    INNER JOIN source_release AS r
        ON pf.release_id = r.release_id AND r.source = 'gnomad'
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
