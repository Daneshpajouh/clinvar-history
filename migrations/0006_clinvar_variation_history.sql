-- Attribute values that a release load overwrote in clinvar_variation, kept
-- so that vwh unload can restore them. One row per variation and release.
CREATE TABLE clinvar_variation_history (
    variation_id BIGINT NOT NULL,
    replaced_by_release_id INTEGER NOT NULL REFERENCES source_release (release_id),
    allele_id BIGINT NOT NULL,
    variant_key TEXT,
    gene_id INTEGER,
    name TEXT,
    variant_type TEXT NOT NULL,
    transcript TEXT,
    hgvs_c TEXT,
    protein_change TEXT,
    hgvs_c_key TEXT,
    hgvs_p_key TEXT,
    PRIMARY KEY (variation_id, replaced_by_release_id)
);
