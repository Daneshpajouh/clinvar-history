-- variant_key holds the full allele text, and the longest ClinVar alleles
-- pass the PostgreSQL B-tree row limit of 2704 bytes. Both engines now key
-- variants by md5(variant_key) so the schema stays the same on each. The
-- loader writes the digest beside every variant_key, and the CHECKs refuse
-- a row whose digest does not match its key.
-- DuckDB cannot change a primary key in place or alter a table that a
-- foreign key references, so the three tables are copied, dropped and
-- created again with the digest as the last column, as ALTER TABLE leaves
-- it on PostgreSQL.
DROP VIEW v_variant_current;

CREATE TEMP TABLE variant_0008 AS
SELECT
    variant_key,
    chrom,
    pos,
    ref,
    alt,
    variant_class
FROM variant;

CREATE TEMP TABLE clinvar_variation_0008 AS
SELECT
    variation_id,
    allele_id,
    variant_key,
    gene_id,
    name,
    variant_type,
    transcript,
    hgvs_c,
    protein_change,
    hgvs_c_key,
    hgvs_p_key,
    first_release_id
FROM clinvar_variation;

CREATE TEMP TABLE population_frequency_0008 AS
SELECT
    variant_key,
    release_id,
    ancestry_group,
    ac,
    an,
    af,
    nhomalt,
    filter
FROM population_frequency;

DROP TABLE population_frequency;
DROP TABLE clinvar_variation;
DROP TABLE variant;

CREATE TABLE variant (
    variant_key TEXT NOT NULL,
    chrom TEXT NOT NULL,
    pos INTEGER NOT NULL CHECK (pos > 0),
    ref TEXT NOT NULL,
    alt TEXT NOT NULL,
    variant_class TEXT NOT NULL
    CHECK (variant_class IN ('snv', 'mnv', 'insertion', 'deletion', 'delins')),
    variant_key_md5 TEXT PRIMARY KEY,
    CHECK (variant_key_md5 = md5(variant_key))
);

CREATE TABLE clinvar_variation (
    variation_id BIGINT PRIMARY KEY,
    allele_id BIGINT NOT NULL,
    variant_key TEXT,
    gene_id INTEGER REFERENCES gene (gene_id),
    name TEXT,
    variant_type TEXT NOT NULL,
    transcript TEXT,
    hgvs_c TEXT,
    protein_change TEXT,
    hgvs_c_key TEXT,
    hgvs_p_key TEXT,
    first_release_id INTEGER NOT NULL REFERENCES source_release (release_id),
    variant_key_md5 TEXT REFERENCES variant (variant_key_md5),
    CHECK (variant_key_md5 IS NOT DISTINCT FROM md5(variant_key))
);

CREATE TABLE population_frequency (
    variant_key TEXT NOT NULL,
    release_id INTEGER NOT NULL REFERENCES source_release (release_id),
    ancestry_group TEXT NOT NULL REFERENCES ancestry_group (code),
    ac INTEGER NOT NULL CHECK (ac >= 0),
    an INTEGER NOT NULL CHECK (an >= 0),
    af DOUBLE PRECISION CHECK (af BETWEEN 0 AND 1),
    nhomalt INTEGER,
    filter TEXT NOT NULL,
    variant_key_md5 TEXT NOT NULL REFERENCES variant (variant_key_md5),
    PRIMARY KEY (variant_key_md5, release_id, ancestry_group),
    CHECK (ac <= an),
    CHECK (variant_key_md5 = md5(variant_key))
);

INSERT INTO variant
SELECT
    variant_key,
    chrom,
    pos,
    ref,
    alt,
    variant_class,
    md5(variant_key) AS variant_key_md5
FROM variant_0008;

INSERT INTO clinvar_variation
SELECT
    variation_id,
    allele_id,
    variant_key,
    gene_id,
    name,
    variant_type,
    transcript,
    hgvs_c,
    protein_change,
    hgvs_c_key,
    hgvs_p_key,
    first_release_id,
    md5(variant_key) AS variant_key_md5
FROM clinvar_variation_0008;

INSERT INTO population_frequency
SELECT
    variant_key,
    release_id,
    ancestry_group,
    ac,
    an,
    af,
    nhomalt,
    filter,
    md5(variant_key) AS variant_key_md5
FROM population_frequency_0008;

DROP TABLE variant_0008;
DROP TABLE clinvar_variation_0008;
DROP TABLE population_frequency_0008;

-- Same columns as 0003; the join now uses the indexed digest.
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
    ON cv.variant_key_md5 = v.variant_key_md5
LEFT JOIN gene AS g
    ON cv.gene_id = g.gene_id;
