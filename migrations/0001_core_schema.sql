-- Core warehouse tables. Written in the SQL subset that DuckDB and
-- PostgreSQL both accept, so one file serves both engines.

CREATE SEQUENCE release_id_seq START 1;
CREATE SEQUENCE provenance_id_seq START 1;
CREATE SEQUENCE classification_id_seq START 1;
CREATE SEQUENCE submitter_id_seq START 1;

CREATE TABLE source_release (
    release_id INTEGER PRIMARY KEY DEFAULT nextval('release_id_seq'),
    source TEXT NOT NULL CHECK (source IN ('clinvar', 'gnomad', 'mavedb')),
    label TEXT NOT NULL,
    release_date DATE,
    -- rolled_back rows stay as an audit record of 'vwh unload'.
    status TEXT NOT NULL CHECK (status IN ('loading', 'loaded', 'rolled_back')),
    loaded_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (source, label)
);

CREATE TABLE provenance (
    provenance_id INTEGER PRIMARY KEY DEFAULT nextval('provenance_id_seq'),
    release_id INTEGER NOT NULL REFERENCES source_release (release_id),
    url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    loaded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    rows_staged BIGINT,
    rows_loaded BIGINT,
    terms TEXT,
    UNIQUE (release_id, local_path)
);

CREATE TABLE review_status (
    review_status TEXT PRIMARY KEY,
    stars SMALLINT NOT NULL CHECK (stars BETWEEN 0 AND 4)
);

CREATE TABLE ancestry_group (
    code TEXT PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE gene (
    gene_id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    hgnc_id TEXT,
    ensembl_id TEXT,
    chrom TEXT,
    start_pos INTEGER,
    end_pos INTEGER,
    in_panel BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (start_pos IS NULL OR end_pos >= start_pos)
);

CREATE TABLE variant (
    variant_key TEXT PRIMARY KEY,
    chrom TEXT NOT NULL,
    pos INTEGER NOT NULL CHECK (pos > 0),
    ref TEXT NOT NULL,
    alt TEXT NOT NULL,
    variant_class TEXT NOT NULL
    CHECK (variant_class IN ('snv', 'mnv', 'insertion', 'deletion', 'delins'))
);

CREATE TABLE clinvar_variation (
    variation_id BIGINT PRIMARY KEY,
    -- Not unique across releases: ClinVar can move an AlleleID to a new
    -- VariationID (AlleleID 3396438 did between 2025-10 and 2026-10).
    -- vwh validate checks uniqueness within the latest release.
    allele_id BIGINT NOT NULL,
    variant_key TEXT REFERENCES variant (variant_key),
    gene_id INTEGER REFERENCES gene (gene_id),
    name TEXT,
    variant_type TEXT NOT NULL,
    transcript TEXT,
    hgvs_c TEXT,
    protein_change TEXT,
    hgvs_c_key TEXT,
    hgvs_p_key TEXT,
    -- Presence in later releases is read from classification, so a release
    -- load rewrites only the rows whose attributes changed.
    first_release_id INTEGER NOT NULL REFERENCES source_release (release_id)
);

CREATE TABLE classification (
    classification_id BIGINT PRIMARY KEY DEFAULT nextval('classification_id_seq'),
    -- No inline foreign key to clinvar_variation: DuckDB 1.5 rejects the
    -- upsert of a referenced parent row. PostgreSQL gets the constraint in
    -- 0004_foreign_keys.postgres.sql; vwh validate checks it on DuckDB.
    variation_id BIGINT NOT NULL,
    clinical_significance TEXT NOT NULL,
    clinsig_class TEXT NOT NULL
    CHECK (clinsig_class IN ('P/LP', 'VUS', 'B/LB', 'Conflicting', 'Other')),
    review_status TEXT NOT NULL REFERENCES review_status (review_status),
    number_submitters INTEGER,
    last_evaluated DATE,
    valid_from_release_id INTEGER NOT NULL REFERENCES source_release (release_id),
    valid_to_release_id INTEGER REFERENCES source_release (release_id),
    is_current BOOLEAN NOT NULL,
    UNIQUE (variation_id, valid_from_release_id),
    CHECK ((is_current AND valid_to_release_id IS NULL) OR (NOT is_current AND valid_to_release_id IS NOT NULL))
);

CREATE TABLE submitter (
    submitter_id INTEGER PRIMARY KEY DEFAULT nextval('submitter_id_seq'),
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE submission (
    release_id INTEGER NOT NULL REFERENCES source_release (release_id),
    scv TEXT NOT NULL,
    scv_version INTEGER NOT NULL,
    variation_id BIGINT NOT NULL,
    submitter_id INTEGER NOT NULL REFERENCES submitter (submitter_id),
    clinical_significance TEXT,
    clinsig_class TEXT NOT NULL
    CHECK (clinsig_class IN ('P/LP', 'VUS', 'B/LB', 'Conflicting', 'Other')),
    date_last_evaluated DATE,
    review_status TEXT,
    collection_method TEXT,
    submitted_gene_symbol TEXT,
    PRIMARY KEY (release_id, scv)
);

CREATE TABLE population_frequency (
    variant_key TEXT NOT NULL REFERENCES variant (variant_key),
    release_id INTEGER NOT NULL REFERENCES source_release (release_id),
    ancestry_group TEXT NOT NULL REFERENCES ancestry_group (code),
    ac INTEGER NOT NULL CHECK (ac >= 0),
    an INTEGER NOT NULL CHECK (an >= 0),
    af DOUBLE PRECISION CHECK (af BETWEEN 0 AND 1),
    nhomalt INTEGER,
    filter TEXT NOT NULL,
    PRIMARY KEY (variant_key, release_id, ancestry_group),
    CHECK (ac <= an)
);

CREATE TABLE score_set (
    urn TEXT PRIMARY KEY,
    release_id INTEGER NOT NULL REFERENCES source_release (release_id),
    title TEXT NOT NULL,
    gene_symbol TEXT NOT NULL,
    gene_id INTEGER REFERENCES gene (gene_id),
    licence TEXT NOT NULL,
    doi TEXT,
    published_date DATE,
    num_variants INTEGER,
    match_level TEXT NOT NULL CHECK (match_level IN ('nucleotide', 'protein')),
    target_accession TEXT
);

CREATE TABLE functional_score (
    variant_urn TEXT PRIMARY KEY,
    score_set_urn TEXT NOT NULL REFERENCES score_set (urn),
    hgvs_nt TEXT,
    hgvs_pro TEXT,
    score DOUBLE PRECISION,
    match_key TEXT
);

