-- Review status to star mapping, from
-- https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/
-- A status missing here fails the load on the foreign key, which is the
-- intended alarm for schema drift in a new ClinVar release.
INSERT INTO review_status (review_status, stars) VALUES
('practice guideline', 4),
('reviewed by expert panel', 3),
('criteria provided, multiple submitters, no conflicts', 2),
('criteria provided, conflicting classifications', 1),
('criteria provided, single submitter', 1),
('no assertion criteria provided', 0),
('no classification provided', 0),
('no classification for the single variant', 0),
('no classifications from unflagged records', 0),
('no assertion provided', 0),
('-', 0);

-- gnomAD v4.1 genetic ancestry groups.
INSERT INTO ancestry_group (code, label) VALUES
('all', 'All samples'),
('afr', 'African/African American'),
('ami', 'Amish'),
('amr', 'Admixed American'),
('asj', 'Ashkenazi Jewish'),
('eas', 'East Asian'),
('fin', 'Finnish'),
('mid', 'Middle Eastern'),
('nfe', 'Non-Finnish European'),
('sas', 'South Asian'),
('remaining', 'Remaining individuals');
