-- The three submitters with the most submissions per panel gene in the latest
-- ClinVar release. Submissions stay separate from the aggregate record, so
-- this counts SCV records, not variants. DENSE_RANK keeps ties.
WITH latest AS (
    SELECT release_id
    FROM v_clinvar_release
    WHERE recency_rank = 1
),

counts AS (
    SELECT
        g.symbol AS gene_symbol,
        su.name AS submitter,
        count(*) AS submissions
    FROM submission AS s
    INNER JOIN latest AS l ON s.release_id = l.release_id
    INNER JOIN clinvar_variation AS cv ON s.variation_id = cv.variation_id
    INNER JOIN gene AS g ON cv.gene_id = g.gene_id
    INNER JOIN submitter AS su ON s.submitter_id = su.submitter_id
    WHERE g.in_panel
    GROUP BY g.symbol, su.name
),

ranked AS (
    SELECT
        gene_symbol,
        submitter,
        submissions,
        dense_rank() OVER (PARTITION BY gene_symbol ORDER BY submissions DESC) AS submitter_rank
    FROM counts
)

SELECT
    gene_symbol,
    submitter_rank,
    submitter,
    submissions
FROM ranked
WHERE submitter_rank <= 3
ORDER BY gene_symbol, submitter_rank, submitter;
