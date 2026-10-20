-- Review stars of the current aggregate records, with the cumulative share at
-- or above each star level (window over an aggregate).
WITH by_star AS (
    SELECT
        stars,
        count(*) AS variants
    FROM v_variant_current
    GROUP BY stars
)

SELECT
    stars,
    variants,
    round(100.0 * variants / sum(variants) OVER (), 2) AS pct,
    round(
        100.0 * sum(variants) OVER (ORDER BY stars DESC) / sum(variants) OVER (), 2
    ) AS cum_pct_at_or_above
FROM by_star
ORDER BY stars DESC;
