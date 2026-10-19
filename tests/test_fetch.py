"""Downloads with curl and bcftools replaced by fakes; no network."""

from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from vwh import fetch
from vwh.config import Paths

CONFIG: dict[str, Any] = {
    "clinvar": {"base_url": "ftp://example.org/clinvar"},
    "panel": {
        "genes": ["BRCA1", "TP53"],
        "ensembl_lookup_url": "https://rest.example.org/lookup",
        "flank_bp": 0,
    },
    "gnomad": {
        "release": "4.1",
        "url_template": "https://example.org/gnomad.chr{chrom}.vcf.bgz",
        "ancestry_groups": ["afr", "nfe"],
    },
    "mavedb": {
        "api": "https://api.example.org",
        "score_sets": [
            {"urn": "urn:mavedb:00000068-0-1", "gene": "TP53", "match_level": "protein"}
        ],
    },
}


class FakeCurl:
    """Stands in for subprocess.run when the command is curl.

    `bodies` maps URL to the bytes a GET returns; `sizes` overrides the
    Content-Length a HEAD request reports; `fail` holds URLs that exit 6.
    """

    def __init__(self) -> None:
        self.bodies: dict[str, bytes] = {}
        self.sizes: dict[str, int] = {}
        self.fail: set[str] = set()
        self.gets: list[str] = []

    def __call__(self, cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        url = cmd[-1]
        if "-sSI" in cmd:
            size = self.sizes.get(url, len(self.bodies.get(url, b"")))
            return subprocess.CompletedProcess(cmd, 0, f"Content-Length: {size}\r\n", "")
        self.gets.append(url)
        if url in self.fail:
            return subprocess.CompletedProcess(cmd, 6, "", "curl: (6) Could not resolve host")
        out = Path(cmd[cmd.index("-o") + 1])
        out.write_bytes(self.bodies[url])
        return subprocess.CompletedProcess(cmd, 0, "", "")


@pytest.fixture
def fake_curl(monkeypatch: pytest.MonkeyPatch) -> FakeCurl:
    fake = FakeCurl()
    monkeypatch.setattr(fetch.subprocess, "run", fake)
    monkeypatch.setattr(fetch.time, "sleep", lambda _s: None)
    return fake


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    return Paths(tmp_path)


def _gz(text: str) -> bytes:
    return gzip.compress(text.encode())


def test_failed_transfer_leaves_no_file(fake_curl: FakeCurl, tmp_path: Path) -> None:
    url = "ftp://example.org/x.gz"
    fake_curl.fail.add(url)
    dest = tmp_path / "x.gz"
    with pytest.raises(fetch.FetchError, match="rc=6"):
        fetch.curl(url, dest)
    assert list(tmp_path.iterdir()) == []


def test_short_transfer_is_rejected(fake_curl: FakeCurl, tmp_path: Path) -> None:
    # The 2026-10 submission file once arrived 62 MB short before a retry.
    url = "ftp://example.org/x.gz"
    fake_curl.bodies[url] = b"partial"
    fake_curl.sizes[url] = 1000
    with pytest.raises(fetch.FetchError, match="server reports 1000"):
        fetch.curl(url, tmp_path / "x.gz", check_size=True)
    assert list(tmp_path.iterdir()) == []


def test_clinvar_fetch_records_hashes_then_reuses(fake_curl: FakeCurl, paths: Paths) -> None:
    base = CONFIG["clinvar"]["base_url"]
    for name in fetch.clinvar_files("2026-10"):
        fake_curl.bodies[f"{base}/{name}"] = _gz(f"{name}\n")
    rows = fetch.fetch_clinvar(CONFIG, paths, "2026-10")
    assert [r["path"] for r in rows] == [
        "raw/clinvar/variant_summary_2026-10.txt.gz",
        "raw/clinvar/submission_summary_2026-10.txt.gz",
    ]
    body = fake_curl.bodies[f"{base}/variant_summary_2026-10.txt.gz"]
    assert rows[0]["sha256"] == hashlib.sha256(body).hexdigest()
    assert rows[0]["size_bytes"] == len(body)
    downloads = len(fake_curl.gets)
    again = fetch.fetch_clinvar(CONFIG, paths, "2026-10")
    assert len(fake_curl.gets) == downloads  # recorded files are not fetched again
    assert [r["sha256"] for r in again] == [r["sha256"] for r in rows]


def test_truncated_gzip_is_rejected(fake_curl: FakeCurl, paths: Paths) -> None:
    base = CONFIG["clinvar"]["base_url"]
    whole = _gz("x" * 10000)
    for name in fetch.clinvar_files("2026-10"):
        fake_curl.bodies[f"{base}/{name}"] = whole[: len(whole) // 2]
    with pytest.raises(fetch.FetchError, match="not a complete gzip stream"):
        fetch.fetch_clinvar(CONFIG, paths, "2026-10")


def test_manifest_keeps_latest_row_per_path(paths: Paths) -> None:
    f = paths.raw / "a.txt"
    f.parent.mkdir(parents=True)
    f.write_text("one")
    fetch.record(paths, source="clinvar", release="r", url="u", path=f, method="m")
    f.write_text("two")
    fetch.record(paths, source="clinvar", release="r", url="u", path=f, method="m")
    rows = fetch.read_manifest(paths)
    assert len(rows) == 1
    assert rows[0]["sha256"] == hashlib.sha256(b"two").hexdigest()


def _ensembl(symbol: str, chrom: str, start: int, end: int, assembly: str = "GRCh38") -> bytes:
    return json.dumps(
        {"id": f"ENSG_{symbol}", "seq_region_name": chrom, "start": start, "end": end,
         "strand": -1, "assembly_name": assembly}
    ).encode()  # fmt: skip


def test_gene_lookup_writes_zero_based_bed(fake_curl: FakeCurl, paths: Paths) -> None:
    base = CONFIG["panel"]["ensembl_lookup_url"]
    fake_curl.bodies[f"{base}/BRCA1?content-type=application/json"] = _ensembl(
        "BRCA1", "17", 43044292, 43170245
    )
    fake_curl.bodies[f"{base}/TP53?content-type=application/json"] = _ensembl(
        "TP53", "17", 7661779, 7687546
    )
    fetch.fetch_genes(CONFIG, paths)
    bed = (paths.raw / "ensembl" / "regions.bed").read_text().splitlines()
    assert bed == ["chr17\t43044291\t43170245\tBRCA1", "chr17\t7661778\t7687546\tTP53"]
    assert [g["symbol"] for g in fetch.panel_regions(paths)] == ["BRCA1", "TP53"]


def test_gene_lookup_rejects_other_assembly(fake_curl: FakeCurl, paths: Paths) -> None:
    base = CONFIG["panel"]["ensembl_lookup_url"]
    for symbol in ("BRCA1", "TP53"):
        fake_curl.bodies[f"{base}/{symbol}?content-type=application/json"] = _ensembl(
            symbol, "17", 1, 2, assembly="GRCh37"
        )
    with pytest.raises(fetch.FetchError, match="unexpected assembly GRCh37"):
        fetch.fetch_genes(CONFIG, paths)


def test_mavedb_records_licence(fake_curl: FakeCurl, paths: Paths) -> None:
    api, urn = CONFIG["mavedb"]["api"], "urn:mavedb:00000068-0-1"
    fake_curl.bodies[f"{api}/score-sets/{urn}"] = json.dumps(
        {"urn": urn, "license": {"shortName": "CC0"}}
    ).encode()
    fake_curl.bodies[f"{api}/score-sets/{urn}/scores"] = b"accession,score\nx#1,0.5\n"
    rows = fetch.fetch_mavedb(CONFIG, paths)
    assert [r["note"] for r in rows] == ["licence CC0", "licence CC0"]
    assert rows[1]["path"] == "raw/mavedb/00000068-0-1.scores.csv"


def test_gnomad_keeps_counts_for_each_group(monkeypatch: pytest.MonkeyPatch, paths: Paths) -> None:
    (paths.raw / "ensembl").mkdir(parents=True)
    (paths.raw / "ensembl" / "genes.json").write_text(
        json.dumps([{"symbol": "TP53", "chrom": "chr17", "start": 7661779, "end": 7687546}])
    )
    calls = []

    def fake_region(url: str, region: str, keep: str, dest: Path, workdir: Path) -> None:
        calls.append((url, region, keep))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_gz("##fileformat=VCFv4.2\n"))

    monkeypatch.setattr(fetch, "_bcftools_region", fake_region)
    rows = fetch.fetch_gnomad(CONFIG, paths)
    url, region, keep = calls[0]
    assert url == "https://example.org/gnomad.chr17.vcf.bgz"
    assert region == "chr17:7661779-7687546"
    # 5 joint fields plus AC, AN, AF and nhomalt for each of 2 groups
    assert len(keep.split(",")) == 13
    assert "INFO/AF_joint_nfe" in keep
    assert rows[0]["source"] == "gnomad"


def test_pipeline_reports_the_failing_stage(tmp_path: Path) -> None:
    out = tmp_path / "out.txt"
    fetch._run_pipe([["printf", "acgt"], ["tr", "a-z", "A-Z"]], out)
    assert out.read_text() == "ACGT"
    with pytest.raises(fetch.FetchError, match="false"):
        fetch._run_pipe([["printf", "x"], ["false"]], tmp_path / "bad.txt")
    assert not (tmp_path / "bad.txt").exists()
