-- variant_key holds the full allele text, and the longest ClinVar alleles
-- pass the B-tree row limit of 2704 bytes, so a full load stopped at the
-- primary key. Keys and foreign keys now use md5(variant_key); a hash index,
-- which has no length limit, serves lookups by the text itself. The loader
-- writes the digest beside every variant_key, and the CHECKs refuse a row
-- whose digest does not match its key.
ALTER TABLE variant ADD COLUMN variant_key_md5 TEXT;
UPDATE variant SET variant_key_md5 = md5(variant_key);
ALTER TABLE variant ALTER COLUMN variant_key_md5 SET NOT NULL;
ALTER TABLE variant ADD CONSTRAINT variant_key_md5_matches
CHECK (variant_key_md5 = md5(variant_key));

ALTER TABLE clinvar_variation ADD COLUMN variant_key_md5 TEXT;
UPDATE clinvar_variation SET variant_key_md5 = md5(variant_key)
WHERE variant_key IS NOT NULL;
ALTER TABLE clinvar_variation ADD CONSTRAINT clinvar_variation_key_md5_matches
CHECK (variant_key_md5 IS NOT DISTINCT FROM md5(variant_key));

ALTER TABLE population_frequency ADD COLUMN variant_key_md5 TEXT;
UPDATE population_frequency SET variant_key_md5 = md5(variant_key);
ALTER TABLE population_frequency ALTER COLUMN variant_key_md5 SET NOT NULL;
ALTER TABLE population_frequency ADD CONSTRAINT population_frequency_key_md5_matches
CHECK (variant_key_md5 = md5(variant_key));

ALTER TABLE clinvar_variation DROP CONSTRAINT clinvar_variation_variant_key_fkey;
ALTER TABLE population_frequency DROP CONSTRAINT population_frequency_variant_key_fkey;
ALTER TABLE population_frequency DROP CONSTRAINT population_frequency_pkey;
ALTER TABLE variant DROP CONSTRAINT variant_pkey;

ALTER TABLE variant ADD PRIMARY KEY (variant_key_md5);
ALTER TABLE population_frequency ADD PRIMARY KEY (variant_key_md5, release_id, ancestry_group);
ALTER TABLE clinvar_variation ADD CONSTRAINT clinvar_variation_variant_key_md5_fkey
FOREIGN KEY (variant_key_md5) REFERENCES variant (variant_key_md5);
ALTER TABLE population_frequency ADD CONSTRAINT population_frequency_variant_key_md5_fkey
FOREIGN KEY (variant_key_md5) REFERENCES variant (variant_key_md5);

CREATE INDEX variant_key_hash ON variant USING hash (variant_key);

-- Same columns as 0003; the join now uses the indexed digest.
CREATE OR REPLACE VIEW v_variant_current AS
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
    ON cv.variant_key_md5 = v.variant_key_md5
LEFT JOIN gene AS g
    ON cv.gene_id = g.gene_id;
