-- Panel P/LP variants with AF >= 0.001 in at least one ancestry group of the
-- latest gnomAD release, with the group where the frequency peaks
-- (ROW_NUMBER picks one row per variant). Same site rules as query 04:
-- FILTER = PASS and AN >= 1000. These are candidates for review, not errors:
-- founder variants and low-penetrance alleles can reach this frequency.
WITH gnomad_latest AS (
    SELECT release_id
    FROM source_release
    WHERE source = 'gnomad' AND status = 'loaded'
    ORDER BY label DESC
    LIMIT 1
),

ranked AS (
    SELECT
        v.gene_symbol,
        v.variant_key,
        v.name,
        v.stars,
        pf.ancestry_group,
        pf.af,
        pf.ac,
        pf.an,
        row_number() OVER (
            PARTITION BY v.variant_key ORDER BY pf.af DESC, pf.ancestry_group
        ) AS rn
    FROM v_variant_current AS v
    INNER JOIN population_frequency AS pf ON md5(v.variant_key) = pf.variant_key_md5
    INNER JOIN gnomad_latest AS g ON pf.release_id = g.release_id
    WHERE
        v.in_panel
        AND v.clinsig_class = 'P/LP'
        AND pf.ancestry_group <> 'all'
        AND pf.filter = 'PASS'
        AND pf.an >= 1000
)

SELECT
    gene_symbol,
    variant_key,
    name,
    stars,
    ancestry_group AS peak_group,
    af AS peak_af,
    ac,
    an
FROM ranked
WHERE rn = 1 AND af >= 0.001
ORDER BY peak_af DESC, variant_key;
