-- Genes with the most variants whose current aggregate ClinVar record is
-- "Conflicting classifications of pathogenicity", and the share of the gene's
-- variants that this represents. Shows a CTE plus a ranking window.
WITH per_gene AS (
    SELECT
        gene_symbol,
        count(*) AS variants,
        sum(CASE WHEN clinsig_class = 'Conflicting' THEN 1 ELSE 0 END) AS conflicting
    FROM v_variant_current
    WHERE gene_symbol IS NOT NULL
    GROUP BY gene_symbol
)

SELECT
    gene_symbol,
    conflicting,
    variants,
    round(100.0 * conflicting / variants, 2) AS pct_conflicting,
    rank() OVER (ORDER BY conflicting DESC) AS conflict_rank
FROM per_gene
WHERE conflicting > 0
ORDER BY conflicting DESC, gene_symbol
LIMIT 15;
