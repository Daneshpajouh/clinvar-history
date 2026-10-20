-- Analyst views. Queries in sql/queries read these rather than the raw joins.

CREATE VIEW v_clinvar_release AS
SELECT
    release_id,
    label,
    row_number() OVER (ORDER BY label DESC) AS recency_rank
FROM source_release
WHERE source = 'clinvar' AND status = 'loaded';

CREATE VIEW v_variant_current AS
SELECT
    cv.variation_id,
    cv.allele_id,
    cv.variant_key,
    v.chrom,
    v.pos,
    v.ref,
    v.alt,
    cv.variant_type,
    g.gene_id,
    g.symbol AS gene_symbol,
    g.in_panel,
    cv.name,
    cv.hgvs_c,
    cv.protein_change,
    c.clinical_significance,
    c.clinsig_class,
    c.review_status,
    rs.stars,
    c.number_submitters,
    c.last_evaluated
FROM clinvar_variation AS cv
INNER JOIN classification AS c
    ON cv.variation_id = c.variation_id AND c.is_current
INNER JOIN review_status AS rs
    ON c.review_status = rs.review_status
LEFT JOIN variant AS v
    ON cv.variant_key = v.variant_key
LEFT JOIN gene AS g
    ON cv.gene_id = g.gene_id;

-- Classification in force at each loaded ClinVar release (SCD type 2 lookup).
CREATE VIEW v_classification_at_release AS
SELECT
    r.release_id,
    r.label AS release_label,
    c.variation_id,
    c.clinical_significance,
    c.clinsig_class,
    c.review_status
FROM v_clinvar_release AS r
INNER JOIN source_release AS r_from
    ON r_from.source = 'clinvar'
INNER JOIN classification AS c
    ON c.valid_from_release_id = r_from.release_id
LEFT JOIN source_release AS r_to
    ON c.valid_to_release_id = r_to.release_id
WHERE
    r_from.label <= r.label
    AND (r_to.label IS NULL OR r_to.label > r.label);
