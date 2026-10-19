"""Synthetic fixtures in the real file formats, small enough to reason about by hand.

The values are invented (gene GENEX, laboratories LabA to LabD) and only the
layouts follow ClinVar, gnomAD and MaveDB. tests/test_queries.py lists the
expected result of every cookbook query on these rows.
"""

from __future__ import annotations

import gzip
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from vwh import load
from vwh.config import Paths
from vwh.db import Engine, connect, migrate
from vwh.fetch import record
from vwh.sources import clinvar, gnomad, mavedb

VS_COLUMNS = [
    "#AlleleID", "Type", "Name", "GeneID", "GeneSymbol", "HGNC_ID", "ClinicalSignificance",
    "ClinSigSimple", "LastEvaluated", "RS# (dbSNP)", "nsv/esv (dbVar)", "RCVaccession",
    "PhenotypeIDS", "PhenotypeList", "Origin", "OriginSimple", "Assembly", "ChromosomeAccession",
    "Chromosome", "Start", "Stop", "ReferenceAllele", "AlternateAllele", "Cytogenetic",
    "ReviewStatus", "NumberSubmitters", "Guidelines", "TestedInGTR", "OtherIDs",
    "SubmitterCategories", "VariationID", "PositionVCF", "ReferenceAlleleVCF",
    "AlternateAlleleVCF", "SomaticClinicalImpact", "SomaticClinicalImpactLastEvaluated",
    "ReviewStatusClinicalImpact", "Oncogenicity", "OncogenicityLastEvaluated",
    "ReviewStatusOncogenicity", "SCVsForAggregateGermlineClassification",
    "SCVsForAggregateSomaticClinicalImpact", "SCVsForAggregateOncogenicityClassification",
]  # fmt: skip

SUB_COLUMNS = [
    "#VariationID", "ClinicalSignificance", "DateLastEvaluated", "Description",
    "SubmittedPhenotypeInfo", "ReportedPhenotypeInfo", "ReviewStatus", "CollectionMethod",
    "OriginCounts", "Submitter", "SCV", "SubmittedGeneSymbol", "ExplanationOfInterpretation",
    "SomaticClinicalImpact", "Oncogenicity", "ContributesToAggregateClassification",
]  # fmt: skip

SINGLE = "criteria provided, single submitter"
MULTI = "criteria provided, multiple submitters, no conflicts"

# (variation, allele, gene_id, symbol, chrom, pos, ref, alt, name, significance, review, n_sub)
V = {
    1: (1001, 2001, 672, "BRCA1", "17", 43045712, "G", "A",
        "NM_007294.4(BRCA1):c.5096G>A (p.Arg1699Gln)"),
    2: (1002, 2002, 672, "BRCA1", "17", 43045713, "C", "T",
        "NM_007294.4(BRCA1):c.5095C>T (p.Arg1699Trp)"),
    3: (1003, 2003, 7157, "TP53", "17", 7675088, "C", "T",
        "NM_000546.6(TP53):c.524G>A (p.Arg175His)"),
    4: (1004, 2004, 7157, "TP53", "17", 7676154, "G", "C",
        "NM_000546.6(TP53):c.215C>G (p.Pro72Arg)"),
    5: (1005, 2005, 9999, "GENEX", "1", 1000, "A", "G",
        "NM_999999.1(GENEX):c.10A>G (p.Lys4Glu)"),
    6: (1006, 2006, 9999, "GENEX", "1", 2000, "AT", "A", "NM_999999.1(GENEX):c.20del (p.Ile7fs)"),
    7: (1007, 2007, 672, "BRCA1", "17", 43045720, "T", "C",
        "NM_007294.4(BRCA1):c.5088A>G (p.Leu1696=)"),
    8: (1008, 2008, 7157, "TP53", "17", 7675089, "G", "A",
        "NM_000546.6(TP53):c.523C>T (p.Arg175Cys)"),
    9: (1009, 2009, 7157, "TP53", "17", 7675090, "T", "C",
        "NM_000546.6(TP53):c.522A>G (p.Arg174=)"),
}  # fmt: skip

RELEASES: dict[str, list[tuple[int, str, str, int]]] = {
    "2025-10": [
        (1, "Uncertain significance", SINGLE, 1),
        (2, "Pathogenic", "reviewed by expert panel", 5),
        (3, "Pathogenic", MULTI, 3),
        (4, "Benign", MULTI, 4),
        (5, "Conflicting classifications of pathogenicity",
         "criteria provided, conflicting classifications", 2),
        (6, "Likely benign", SINGLE, 1),
        (7, "Benign", "no assertion criteria provided", 1),
    ],
    "2026-10": [
        (1, "Likely pathogenic", SINGLE, 2),
        (2, "Pathogenic", "reviewed by expert panel", 5),
        (3, "Pathogenic", MULTI, 3),
        (4, "Likely benign", MULTI, 4),
        (5, "Conflicting classifications of pathogenicity",
         "criteria provided, conflicting classifications", 2),
        (7, "Benign", "no assertion criteria provided", 1),
        (8, "Likely pathogenic", SINGLE, 1),
        (9, "Benign", SINGLE, 1),
    ],
}  # fmt: skip

# (variation, scv with version, submitter, significance)
SUBMISSIONS = {
    "2025-10": [
        (1002, "SCV0000002.1", "LabB", "Uncertain significance"),
        (1002, "SCV0000003.1", "LabA", "Pathogenic"),
        (1004, "SCV0000008.1", "LabB", "Benign"),
        (1006, "SCV0000015.1", "LabC", "Likely benign"),
    ],
    "2026-10": [
        (1001, "SCV0000001.1", "LabA", "Likely pathogenic"),
        (1001, "SCV0000002.1", "LabB", "Uncertain significance"),
        (1002, "SCV0000003.2", "LabA", "Pathogenic"),
        (1002, "SCV0000004.1", "ExpertPanel", "Pathogenic"),
        (1003, "SCV0000005.1", "LabA", "Pathogenic"),
        (1003, "SCV0000006.1", "LabB", "Pathogenic"),
        (1003, "SCV0000007.1", "LabC", "Pathogenic"),
        (1004, "SCV0000008.1", "LabB", "Likely benign"),
        (1005, "SCV0000009.1", "LabC", "Pathogenic"),
        (1005, "SCV0000010.1", "LabD", "Benign"),
        (1007, "SCV0000011.1", "LabD", "Benign"),
        (1007, "SCV0000011.1", "LabD", "not provided"),  # repeated SCV, dropped
        (1008, "SCV0000012.1", "LabA", "Likely pathogenic"),
        (1009, "SCV0000013.1", "LabB", "Benign"),
        (5555, "SCV0000014.1", "LabA", "Pathogenic"),  # VariationID not in variant_summary
    ],
}

GROUPS = ["afr", "nfe"]
# key -> {group: (ac, an, af)}
GNOMAD = {
    ("17", 43045712, "G", "A"): {"all": (5, 10000, 0.0005), "afr": (4, 2000, 0.002),
                                 "nfe": (1, 6000, 0.000166667)},
    ("17", 7675088, "C", "T"): {"all": (1, 10000, 0.0001), "afr": (0, 2000, 0.0),
                                "nfe": (1, 6000, 0.000166667)},
    ("17", 7676154, "G", "C"): {"all": (3000, 10000, 0.3), "afr": (600, 2000, 0.3),
                                "nfe": (1800, 6000, 0.3)},
}  # fmt: skip

SCORE_SETS = [
    {"urn": "urn:mavedb:00000097-0-2", "gene": "BRCA1", "match_level": "nucleotide",
     "target": {"accession": "NM_007294.3"},
     "scores": [("NM_007294.3:c.5096G>A", None, -2.0), ("NM_007294.3:c.5095C>T", None, -1.5),
                ("NM_007294.3:c.5088A>G", None, 0.5), ("NM_007294.3:c.5000A>G", None, 0.1)]},
    {"urn": "urn:mavedb:00000068-0-1", "gene": "TP53", "match_level": "protein", "target": None,
     "scores": [(None, "p.Arg175His", -3.0), (None, "p.Arg175Cys", -1.0),
                (None, "p.Pro72Arg", 1.0), (None, "p.Arg174=", 0.8), (None, "p.Met1Ala", 0.0)]},
]  # fmt: skip

GENES = [
    {"symbol": "BRCA1", "ensembl_id": "ENSG00000012048", "chrom": "chr17", "start": 43044292,
     "end": 43170245, "strand": -1, "assembly": "GRCh38"},
    {"symbol": "TP53", "ensembl_id": "ENSG00000141510", "chrom": "chr17", "start": 7661779,
     "end": 7687546, "strand": -1, "assembly": "GRCh38"},
]  # fmt: skip


def _variant_summary_rows(release: str) -> list[list[str]]:
    rows = []
    for idx, sig, review, n_sub in RELEASES[release]:
        vid, aid, gid, sym, chrom, pos, ref, alt, name = V[idx]
        for assembly in ("GRCh37", "GRCh38"):
            row = dict.fromkeys(VS_COLUMNS, "-")
            row.update({
                "#AlleleID": str(aid), "Type": "single nucleotide variant", "Name": name,
                "GeneID": str(gid), "GeneSymbol": sym, "ClinicalSignificance": sig,
                "LastEvaluated": "Jan 05, 2025", "Assembly": assembly, "Chromosome": chrom,
                "ReviewStatus": review, "NumberSubmitters": str(n_sub), "VariationID": str(vid),
                "PositionVCF": str(pos if assembly == "GRCh38" else pos + 100),
                "ReferenceAlleleVCF": ref, "AlternateAlleleVCF": alt,
            })  # fmt: skip
            rows.append([row[c] for c in VS_COLUMNS])
    return rows


def _write_gz(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as fh:
        fh.write(text)


def build_raw(paths: Paths) -> None:
    for release in RELEASES:
        vs = paths.raw / "clinvar" / f"variant_summary_{release}.txt.gz"
        lines = ["\t".join(VS_COLUMNS)] + ["\t".join(r) for r in _variant_summary_rows(release)]
        _write_gz(vs, "\n".join(lines) + "\n")
        sub = paths.raw / "clinvar" / f"submission_summary_{release}.txt.gz"
        head = [
            "##Overview of interpretation, phenotypes, observations, and methods",
            "#VariationID:                   the identifier assigned by ClinVar",
            "\t".join(SUB_COLUMNS),
        ]
        body = []
        for vid, scv, who, sig in SUBMISSIONS[release]:
            row = dict.fromkeys(SUB_COLUMNS, "-")
            row.update({
                "#VariationID": str(vid), "ClinicalSignificance": sig,
                "DateLastEvaluated": "Mar 01, 2025", "ReviewStatus": SINGLE,
                "CollectionMethod": "clinical testing", "Submitter": who, "SCV": scv,
            })  # fmt: skip
            body.append("\t".join(row[c] for c in SUB_COLUMNS))
        _write_gz(sub, "\n".join(head + body) + "\n")
        for path in (vs, sub):
            record(paths, source="clinvar", release=release, url=f"fixture://{path.name}",
                   path=path, method="fixture")  # fmt: skip

    (paths.raw / "ensembl").mkdir(parents=True, exist_ok=True)
    (paths.raw / "ensembl" / "genes.json").write_text(json.dumps(GENES))

    vcf = ["##fileformat=VCFv4.2", "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO"]
    for (chrom, pos, ref, alt), groups in GNOMAD.items():
        info = []
        for grp, (ac, an, af) in groups.items():
            sfx = "_joint" if grp == "all" else f"_joint_{grp}"
            info += [f"AC{sfx}={ac}", f"AN{sfx}={an}", f"AF{sfx}={af}", f"nhomalt{sfx}=0"]
        vcf.append(f"chr{chrom}\t{pos}\t.\t{ref}\t{alt}\t.\tPASS\t{';'.join(info)}")
    gpath = paths.raw / "gnomad" / "gnomad.joint.v4.1.FIXTURE.vcf.gz"
    _write_gz(gpath, "\n".join(vcf) + "\n")
    record(paths, source="gnomad", release="4.1", url="fixture://gnomad", path=gpath,
           method="fixture")  # fmt: skip

    for ss in SCORE_SETS:
        slug = str(ss["urn"]).replace("urn:mavedb:", "")
        meta = {
            "urn": ss["urn"], "title": f"Fixture {ss['gene']} scores",
            "license": {"shortName": "CC0"}, "publishedDate": "2020-01-01",
            "numVariants": len(ss["scores"]),
            "targetGenes": [{"name": ss["gene"], "targetAccession": ss["target"]}],
            "primaryPublicationIdentifiers": [],
        }  # fmt: skip
        mpath = paths.raw / "mavedb" / f"{slug}.json"
        mpath.parent.mkdir(parents=True, exist_ok=True)
        mpath.write_text(json.dumps(meta))
        lines = ["accession,hgvs_nt,hgvs_splice,hgvs_pro,score"]
        for i, (nt, pro, score) in enumerate(ss["scores"], start=1):
            lines.append(f"{ss['urn']}#{i},{nt or 'NA'},NA,{pro or 'NA'},{score}")
        spath = paths.raw / "mavedb" / f"{slug}.scores.csv"
        spath.write_text("\n".join(lines) + "\n")
        for path in (mpath, spath):
            record(paths, source="mavedb", release=str(ss["urn"]), url=f"fixture://{path.name}",
                   path=path, method="fixture")  # fmt: skip


def mave_config() -> list[dict[str, Any]]:
    return [{"urn": s["urn"], "gene": s["gene"], "match_level": s["match_level"]} for s in SCORE_SETS]


def stage_all(paths: Paths) -> None:
    for release in RELEASES:
        clinvar.stage_release(paths.raw / "clinvar", paths.staging, release)
    gnomad.stage(paths.raw / "gnomad", paths.staging, GROUPS, "4.1")
    mavedb.stage(paths.raw / "mavedb", paths.staging, mave_config())


def load_all(engine: Engine, paths: Paths) -> None:
    migrate(engine)
    for release in sorted(RELEASES):
        load.load_clinvar(engine, paths, release)
    load.load_panel(engine, paths)
    load.load_gnomad(engine, paths, "4.1")
    load.load_mavedb(engine, paths)


@pytest.fixture(scope="session")
def fixture_paths(tmp_path_factory: pytest.TempPathFactory) -> Paths:
    paths = Paths(tmp_path_factory.mktemp("vwh-data"))
    build_raw(paths)
    stage_all(paths)
    return paths


def reset_postgres(dsn: str, schema: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


ENGINES = ["duckdb"] + (["postgres"] if os.environ.get("VWH_PG_DSN") else [])


@pytest.fixture(params=ENGINES)
def empty_engine(request: pytest.FixtureRequest) -> Iterator[Engine]:
    if request.param == "postgres":
        dsn = os.environ["VWH_PG_DSN"]
        reset_postgres(dsn, "vwh_test_empty")
        engine = connect(dsn=dsn, schema="vwh_test_empty")
    else:
        engine = connect()
    yield engine
    engine.close()


@pytest.fixture(scope="session", params=ENGINES)
def loaded_engine(request: pytest.FixtureRequest, fixture_paths: Paths) -> Iterator[Engine]:
    if request.param == "postgres":
        dsn = os.environ["VWH_PG_DSN"]
        reset_postgres(dsn, "vwh_test_loaded")
        engine = connect(dsn=dsn, schema="vwh_test_loaded")
    else:
        engine = connect()
    load_all(engine, fixture_paths)
    yield engine
    engine.close()
