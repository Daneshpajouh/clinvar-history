-- Class changes of the aggregate germline record between the two most recent
-- loaded ClinVar releases, for variations present in both. Reads the SCD type 2
-- history through v_classification_at_release.
WITH pair AS (
    SELECT
        max(CASE WHEN recency_rank = 2 THEN release_id END) AS old_id,
        max(CASE WHEN recency_rank = 1 THEN release_id END) AS new_id
    FROM v_clinvar_release
),

old_c AS (
    SELECT
        a.variation_id,
        a.clinsig_class
    FROM v_classification_at_release AS a
    INNER JOIN pair ON a.release_id = pair.old_id
),

new_c AS (
    SELECT
        a.variation_id,
        a.clinsig_class
    FROM v_classification_at_release AS a
    INNER JOIN pair ON a.release_id = pair.new_id
)

SELECT
    o.clinsig_class AS from_class,
    n.clinsig_class AS to_class,
    count(*) AS variations
FROM old_c AS o
INNER JOIN new_c AS n ON o.variation_id = n.variation_id
WHERE o.clinsig_class <> n.clinsig_class
GROUP BY o.clinsig_class, n.clinsig_class
ORDER BY variations DESC, from_class, to_class;
