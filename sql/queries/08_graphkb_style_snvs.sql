-- Current P/LP single nucleotide variants in the panel genes written in a
-- GraphKB-style genomic notation, for example chr17:g.43045712G>A on hg38.
-- Indels are left out: the warehouse stores VCF left-aligned alleles, while
-- HGVS places indels at the 3' most position, and converting between the two
-- needs the reference sequence.
SELECT
    gene_symbol,
    variant_key,
    'chr' || chrom || ':g.' || cast(pos AS TEXT) || ref || '>' || alt AS graphkb_style,
    clinical_significance,
    stars
FROM v_variant_current
WHERE
    in_panel
    AND clinsig_class = 'P/LP'
    AND length(ref) = 1
    AND length(alt) = 1
ORDER BY gene_symbol, chrom, pos, alt;
