-- Agreement between MaveDB functional scores and ClinVar classes.
--
-- Joins: nucleotide score sets match clinvar_variation.hgvs_c_key (same
-- transcript, version ignored, same c. change). Protein score sets match
-- hgvs_p_key (gene plus single amino acid change); several nucleotide changes
-- can give one protein change, so a protein change is labelled only when every
-- matched ClinVar variation with at least one star agrees on P/LP or B/LB.
--
-- auc_plp_lower is the Mann-Whitney estimate of P(score of a P/LP variant <
-- score of a B/LB variant), ties counted as one half. 0.5 means no separation.
-- Assays differ in direction, so a value near 0 separates as well as one near 1.
WITH matched AS (
    SELECT
        fs.score_set_urn,
        fs.match_key,
        fs.score,
        cv.variation_id,
        v.clinsig_class
    FROM functional_score AS fs
    INNER JOIN score_set AS ss ON fs.score_set_urn = ss.urn
    INNER JOIN clinvar_variation AS cv
        ON (ss.match_level = 'nucleotide' AND fs.match_key = cv.hgvs_c_key)
        OR (ss.match_level = 'protein' AND fs.match_key = cv.hgvs_p_key)
    INNER JOIN v_variant_current AS v ON cv.variation_id = v.variation_id
    WHERE
        fs.score IS NOT NULL
        AND v.stars >= 1
        AND v.clinsig_class IN ('P/LP', 'B/LB')
),

labelled AS (
    SELECT
        score_set_urn,
        match_key,
        min(score) AS score,
        min(clinsig_class) AS clinsig_class
    FROM matched
    GROUP BY score_set_urn, match_key
    HAVING count(DISTINCT clinsig_class) = 1
),

ranked AS (
    SELECT
        score_set_urn,
        clinsig_class,
        score,
        (
            rank() OVER w
            + count(*) OVER w
        ) / 2.0 AS avg_rank
    FROM labelled
    WINDOW w AS (PARTITION BY score_set_urn ORDER BY score)
),

per_set AS (
    SELECT
        score_set_urn,
        sum(CASE WHEN clinsig_class = 'P/LP' THEN 1 ELSE 0 END) AS n_plp,
        sum(CASE WHEN clinsig_class = 'B/LB' THEN 1 ELSE 0 END) AS n_blb,
        sum(CASE WHEN clinsig_class = 'B/LB' THEN avg_rank ELSE 0 END) AS rank_sum_blb
    FROM ranked
    GROUP BY score_set_urn
),

medians AS (
    SELECT
        score_set_urn,
        percentile_cont(0.5) WITHIN GROUP (
            ORDER BY CASE WHEN clinsig_class = 'P/LP' THEN score END
        ) AS median_plp,
        percentile_cont(0.5) WITHIN GROUP (
            ORDER BY CASE WHEN clinsig_class = 'B/LB' THEN score END
        ) AS median_blb
    FROM labelled
    GROUP BY score_set_urn
)

SELECT
    ss.gene_symbol,
    ss.urn,
    ss.match_level,
    p.n_plp,
    p.n_blb,
    round(cast(m.median_plp AS numeric), 3) AS median_plp,
    round(cast(m.median_blb AS numeric), 3) AS median_blb,
    round(
        cast(
            (p.rank_sum_blb - p.n_blb * (p.n_blb + 1) / 2.0) / (p.n_plp * p.n_blb) AS numeric
        ),
        3
    ) AS auc_plp_lower
FROM per_set AS p
INNER JOIN medians AS m ON p.score_set_urn = m.score_set_urn
INNER JOIN score_set AS ss ON p.score_set_urn = ss.urn
WHERE p.n_plp > 0 AND p.n_blb > 0
ORDER BY ss.gene_symbol, ss.urn;
