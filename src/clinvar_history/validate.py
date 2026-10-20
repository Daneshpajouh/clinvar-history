"""Post-load checks. Each check is a SQL count that must be zero, or a comparison."""

from __future__ import annotations

from dataclasses import dataclass

from clinvar_history.db import Engine

# name -> SQL returning the number of violating rows
ZERO_CHECKS: dict[str, str] = {
    "variant key matches chrom-pos-ref-alt": (
        "SELECT count(*) FROM variant WHERE variant_key <>"
        " chrom || '-' || cast(pos AS TEXT) || '-' || ref || '-' || alt"
    ),
    "alleles use only A, C, G, T, N": (
        "SELECT count(*) FROM variant WHERE length(ref) = 0 OR length(alt) = 0"
        " OR length(replace(replace(replace(replace(replace(ref || alt,"
        " 'A', ''), 'C', ''), 'G', ''), 'T', ''), 'N', '')) > 0"
    ),
    "one current classification per variation": (
        "SELECT count(*) FROM (SELECT variation_id FROM classification WHERE is_current"
        " GROUP BY variation_id HAVING count(*) > 1) AS d"
    ),
    "classification versions do not overlap": (
        "SELECT count(*) FROM classification AS a INNER JOIN classification AS b"
        " ON a.variation_id = b.variation_id AND a.classification_id < b.classification_id"
        " INNER JOIN source_release AS af ON a.valid_from_release_id = af.release_id"
        " INNER JOIN source_release AS bf ON b.valid_from_release_id = bf.release_id"
        " LEFT JOIN source_release AS a_to ON a.valid_to_release_id = a_to.release_id"
        " LEFT JOIN source_release AS b_to ON b.valid_to_release_id = b_to.release_id"
        " WHERE af.label < coalesce(b_to.label, '9999') AND bf.label < coalesce(a_to.label, '9999')"
    ),
    "classification rows reference a ClinVar variation": (
        "SELECT count(*) FROM classification AS c LEFT JOIN clinvar_variation AS cv"
        " ON c.variation_id = cv.variation_id WHERE cv.variation_id IS NULL"
    ),
    "submission rows reference a ClinVar variation": (
        "SELECT count(*) FROM submission AS s LEFT JOIN clinvar_variation AS cv"
        " ON s.variation_id = cv.variation_id WHERE cv.variation_id IS NULL"
    ),
    "every ClinVar variation has a classification history": (
        "SELECT count(*) FROM clinvar_variation AS cv LEFT JOIN classification AS c"
        " ON c.variation_id = cv.variation_id WHERE c.variation_id IS NULL"
    ),
    "AlleleID unique among current variations": (
        "SELECT count(*) FROM (SELECT cv.allele_id FROM clinvar_variation AS cv"
        " INNER JOIN classification AS c ON c.variation_id = cv.variation_id AND c.is_current"
        " GROUP BY cv.allele_id HAVING count(*) > 1) AS d"
    ),
    "gnomAD AF agrees with AC/AN (abs diff < 1e-4)": (
        "SELECT count(*) FROM population_frequency WHERE an > 0 AND af IS NOT NULL"
        " AND abs(af - cast(ac AS DOUBLE PRECISION) / an) >= 1e-4"
    ),
    "gnomAD rows reference a known variant": (
        "SELECT count(*) FROM population_frequency AS pf LEFT JOIN variant AS v"
        " ON pf.variant_key_md5 = v.variant_key_md5 WHERE v.variant_key_md5 IS NULL"
    ),
    "score sets carry a licence": (
        "SELECT count(*) FROM score_set WHERE licence IS NULL OR licence = ''"
    ),
    "functional scores reference a score set": (
        "SELECT count(*) FROM functional_score AS f LEFT JOIN score_set AS s"
        " ON f.score_set_urn = s.urn WHERE s.urn IS NULL"
    ),
    "provenance SHA-256 values are 64 hex characters": (
        "SELECT count(*) FROM provenance WHERE length(sha256) <> 64"
        " OR length(replace(replace(replace(replace(replace(replace(replace(replace(replace("
        "replace(replace(replace(replace(replace(replace(replace(sha256, '0', ''), '1', ''),"
        " '2', ''), '3', ''), '4', ''), '5', ''), '6', ''), '7', ''), '8', ''), '9', ''),"
        " 'a', ''), 'b', ''), 'c', ''), 'd', ''), 'e', ''), 'f', '')) > 0"
    ),
    "releases left in 'loading' state": (
        "SELECT count(*) FROM source_release WHERE status = 'loading'"
    ),
}


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def run_checks(engine: Engine) -> list[CheckResult]:
    results = []
    for name, sql in ZERO_CHECKS.items():
        n = int(engine.scalar(sql))
        results.append(CheckResult(name, n == 0, f"{n} violating rows"))
    # Row reconciliation: rows loaded must equal rows staged for each file that
    # records both. Submissions differ by design (orphans), so they are reported.
    _, rows = engine.query(
        "SELECT r.source, r.label, p.local_path, p.rows_staged, p.rows_loaded"
        " FROM provenance AS p INNER JOIN source_release AS r ON p.release_id = r.release_id"
        " WHERE p.rows_staged IS NOT NULL ORDER BY r.source, r.label, p.local_path"
    )
    for source, label, path, staged, loaded in rows:
        is_sub = "submission_summary" in path
        ok = staged == loaded or is_sub
        detail = f"staged {staged}, loaded {loaded}"
        if is_sub:
            detail += f"; {staged - loaded} rows name a VariationID absent from variant_summary"
        results.append(
            CheckResult(f"row counts {source} {label} {path.split('/')[-1]}", ok, detail)
        )
    return results


def to_markdown(results: list[CheckResult], engine_name: str) -> str:
    lines = [
        f"| Check ({engine_name}) | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for r in results:
        lines.append(f"| {r.name} | {'pass' if r.passed else 'FAIL'} | {r.detail} |")
    return "\n".join(lines) + "\n"
