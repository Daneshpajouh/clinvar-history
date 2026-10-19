-- Foreign keys that DuckDB cannot keep while clinvar_variation is upserted.
ALTER TABLE classification
ADD CONSTRAINT classification_variation_fk
FOREIGN KEY (variation_id) REFERENCES clinvar_variation (variation_id);

ALTER TABLE submission
ADD CONSTRAINT submission_variation_fk
FOREIGN KEY (variation_id) REFERENCES clinvar_variation (variation_id);
