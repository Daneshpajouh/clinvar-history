"""Download raw inputs and record each file in a JSON-lines manifest.

Every file lands under <data_dir>/raw/<source>/ through a temporary name and is
renamed only after the transfer tool exits 0 and the file is non-empty. The
manifest row (URL, size, SHA-256, fetch time, terms) feeds the provenance table.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from clinvar_history.config import Paths
from clinvar_history.logs import get_logger

log = get_logger(__name__)

BCFTOOLS = shutil.which("bcftools") or "bcftools"

TERMS = {
    "clinvar": "NCBI: no restrictions on use or distribution; "
    "https://www.ncbi.nlm.nih.gov/home/about/policies/",
    "gnomad": "gnomAD primary data CC0 1.0; some annotations carry their own terms; "
    "https://gnomad.broadinstitute.org/policies",
    "mavedb": "Per score set licence, recorded in score_set.licence",
    "ensembl": "Ensembl: no restrictions on access to or use of its data; "
    "https://mart.ensembl.org/info/about/legal/disclaimer.html",
}


class FetchError(RuntimeError):
    pass


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def record(
    paths: Paths,
    *,
    source: str,
    release: str,
    url: str,
    path: Path,
    method: str,
    note: str = "",
) -> dict[str, Any]:
    row = {
        "source": source,
        "release": release,
        "url": url,
        "path": str(path.relative_to(paths.data_dir)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "fetched_at": _now(),
        "terms": TERMS.get(source, ""),
        "method": method,
        "note": note,
    }
    paths.manifest.parent.mkdir(parents=True, exist_ok=True)
    with paths.manifest.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    log.info("fetched", extra={k: row[k] for k in ("source", "path", "size_bytes", "sha256")})
    return row


def read_manifest(paths: Paths) -> list[dict[str, Any]]:
    """Latest manifest row per path; earlier rows for the same path are superseded."""
    if not paths.manifest.exists():
        return []
    latest: dict[str, dict[str, Any]] = {}
    for line in paths.manifest.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            latest[row["path"]] = row
    return list(latest.values())


def remote_size(url: str) -> int | None:
    """Content-Length from a HEAD request (FTP servers report SIZE the same way)."""
    proc = subprocess.run(
        ["curl", "-sSI", "-L", "-m", "60", url],
        capture_output=True,
        text=True,
        check=False,
    )
    sizes = [
        int(line.split(":", 1)[1])
        for line in proc.stdout.splitlines()
        if line.lower().startswith("content-length:")
    ]
    return sizes[-1] if proc.returncode == 0 and sizes else None


def curl(
    url: str,
    dest: Path,
    *,
    max_time: int = 3600,
    accept: str | None = None,
    check_size: bool = False,
) -> None:
    """Fetch one URL with curl. The exit code is read before anything else runs."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(f".{dest.name}.part")
    cmd = [
        "curl",
        "-sS",
        "--fail",
        "-L",
        "-m",
        str(max_time),
        "--connect-timeout",
        "60",
        "--retry",
        "5",
        "--retry-delay",
        "20",
        "--retry-all-errors",
        "-o",
        str(part),
        url,
    ]
    if accept:
        cmd[1:1] = ["-H", f"Accept: {accept}"]
    started = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    rc = proc.returncode
    if rc != 0 or not part.exists() or part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        raise FetchError(f"curl rc={rc} for {url}: {proc.stderr.strip()}")
    if check_size:
        expected = remote_size(url)
        got = part.stat().st_size
        if expected is not None and expected != got:
            part.unlink(missing_ok=True)
            raise FetchError(f"{url}: got {got} bytes, server reports {expected}")
    part.replace(dest)
    log.info(
        "download",
        extra={
            "url": url,
            "bytes": dest.stat().st_size,
            "seconds": round(time.monotonic() - started, 1),
        },
    )


def _gzip_ok(path: Path) -> bool:
    try:
        with gzip.open(path, "rb") as fh:
            while fh.read(1 << 24):
                pass
    except (OSError, EOFError):
        return False
    return True


# ---------------------------------------------------------------- ClinVar


def clinvar_files(release: str) -> list[str]:
    return [f"variant_summary_{release}.txt.gz", f"submission_summary_{release}.txt.gz"]


def fetch_clinvar(cfg: dict[str, Any], paths: Paths, release: str) -> list[dict[str, Any]]:
    out = []
    known = {row["path"]: row for row in read_manifest(paths)}
    for name in clinvar_files(release):
        dest = paths.raw / "clinvar" / name
        url = f"{cfg['clinvar']['base_url']}/{name}"
        rel = str(dest.relative_to(paths.data_dir))
        if dest.exists() and rel in known:
            out.append(known[rel])
            continue
        method = "reused existing file"
        if not dest.exists():
            curl(url, dest, check_size=True)
            method = "curl over FTP"
        expected = remote_size(url)
        if expected is not None and expected != dest.stat().st_size:
            raise FetchError(f"{dest}: {dest.stat().st_size} bytes, server reports {expected}")
        if not _gzip_ok(dest):
            raise FetchError(f"{dest} is not a complete gzip stream")
        out.append(
            record(paths, source="clinvar", release=release, url=url, path=dest, method=method)
        )
    return out


# ---------------------------------------------------------------- genes


def fetch_genes(cfg: dict[str, Any], paths: Paths) -> dict[str, Any]:
    """Look up GRCh38 coordinates for the panel genes and write genes.json and regions.bed."""
    base = cfg["panel"]["ensembl_lookup_url"]
    genes = []
    tmp = paths.raw / "ensembl" / "tmp"
    for symbol in cfg["panel"]["genes"]:
        dest = tmp / f"{symbol}.json"
        curl(f"{base}/{symbol}?content-type=application/json", dest, max_time=60)
        data = json.loads(dest.read_text())
        if data.get("assembly_name") != "GRCh38":
            raise FetchError(f"{symbol}: unexpected assembly {data.get('assembly_name')}")
        genes.append(
            {
                "symbol": symbol,
                "ensembl_id": data["id"],
                "chrom": f"chr{data['seq_region_name']}",
                "start": int(data["start"]),
                "end": int(data["end"]),
                "strand": int(data["strand"]),
                "assembly": data["assembly_name"],
            }
        )
        time.sleep(0.1)  # Ensembl REST asks for at most 15 requests a second
    shutil.rmtree(tmp)
    out = paths.raw / "ensembl" / "genes.json"
    out.write_text(json.dumps(genes, indent=1) + "\n")
    flank = int(cfg["panel"]["flank_bp"])
    bed = paths.raw / "ensembl" / "regions.bed"
    bed.write_text(
        "".join(
            f"{g['chrom']}\t{g['start'] - 1 - flank}\t{g['end'] + flank}\t{g['symbol']}\n"
            for g in genes
        )
    )
    return record(
        paths,
        source="ensembl",
        release="GRCh38",
        url=base,
        path=out,
        method="Ensembl REST lookup/symbol per gene",
    )


def panel_regions(paths: Paths) -> list[dict[str, Any]]:
    genes: list[dict[str, Any]] = json.loads((paths.raw / "ensembl" / "genes.json").read_text())
    return genes


def _region(g: dict[str, Any]) -> str:
    return f"{g['chrom']}:{g['start']}-{g['end']}"


# ---------------------------------------------------------------- gnomAD

GNOMAD_FIELDS = ["AC_joint", "AN_joint", "AF_joint", "nhomalt_joint", "grpmax_joint"]


def gnomad_info_fields(groups: Iterable[str]) -> list[str]:
    fields = list(GNOMAD_FIELDS)
    for grp in groups:
        fields += [f"AC_joint_{grp}", f"AN_joint_{grp}", f"AF_joint_{grp}", f"nhomalt_joint_{grp}"]
    return fields


def _run_pipe(cmds: list[list[str]], dest: Path) -> None:
    """Run a pipeline of commands; fail if any stage exits non-zero."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(f".{dest.name}.part")
    procs: list[subprocess.Popen[bytes]] = []
    prev = None
    with part.open("wb") as out:
        for i, cmd in enumerate(cmds):
            last = i == len(cmds) - 1
            p = subprocess.Popen(
                cmd, stdin=prev, stdout=out if last else subprocess.PIPE, stderr=subprocess.PIPE
            )
            if prev is not None:
                prev.close()
            prev = p.stdout
            procs.append(p)
        errors = []
        for cmd, p in zip(cmds, procs, strict=True):
            _, err = p.communicate()
            if p.returncode != 0:
                stage = " ".join(cmd[:2])
                errors.append(f"{stage} rc={p.returncode}: {err.decode()[-500:]}")
    if errors:
        part.unlink(missing_ok=True)
        raise FetchError("; ".join(errors))
    part.replace(dest)


def fetch_gnomad(cfg: dict[str, Any], paths: Paths) -> list[dict[str, Any]]:
    keep = ",".join(f"INFO/{f}" for f in gnomad_info_fields(cfg["gnomad"]["ancestry_groups"]))
    out = []
    for g in panel_regions(paths):
        chrom = g["chrom"].removeprefix("chr")
        url = cfg["gnomad"]["url_template"].format(chrom=chrom)
        dest = paths.raw / "gnomad" / f"gnomad.joint.v4.1.{g['symbol']}.vcf.gz"
        _bcftools_region(url, _region(g), keep, dest, paths.raw / "gnomad")
        out.append(
            record(
                paths,
                source="gnomad",
                release=cfg["gnomad"]["release"],
                url=url,
                path=dest,
                method=(
                    f"bcftools view -r {_region(g)} | annotate -x ^<{len(keep.split(','))} fields>"
                ),
            )
        )
    return out


def _bcftools_region(url: str, region: str, keep: str, dest: Path, workdir: Path) -> None:
    # htslib caches the remote .tbi in the working directory, so run from the
    # raw folder rather than the repository.
    view = [BCFTOOLS, "view", "-r", region, "-Ou", url]
    tail = [BCFTOOLS, "annotate", "-x", f"^{keep}", "-Oz"]
    workdir.mkdir(parents=True, exist_ok=True)
    cwd = Path.cwd()
    try:
        os.chdir(workdir)
        _run_pipe([view, tail], dest)
    finally:
        os.chdir(cwd)
    subprocess.run([BCFTOOLS, "index", "-f", "-t", str(dest)], check=True)


# ---------------------------------------------------------------- MaveDB


def fetch_mavedb(cfg: dict[str, Any], paths: Paths) -> list[dict[str, Any]]:
    api = cfg["mavedb"]["api"]
    out = []
    for ss in cfg["mavedb"]["score_sets"]:
        urn = ss["urn"]
        slug = urn.replace("urn:mavedb:", "")
        meta = paths.raw / "mavedb" / f"{slug}.json"
        scores = paths.raw / "mavedb" / f"{slug}.scores.csv"
        curl(f"{api}/score-sets/{urn}", meta, max_time=120)
        curl(f"{api}/score-sets/{urn}/scores", scores, max_time=600)
        licence = json.loads(meta.read_text()).get("license", {}).get("shortName", "unknown")
        for path, url in (
            (meta, f"{api}/score-sets/{urn}"),
            (scores, f"{api}/score-sets/{urn}/scores"),
        ):
            out.append(
                record(
                    paths,
                    source="mavedb",
                    release=urn,
                    url=url,
                    path=path,
                    method="MaveDB API v1",
                    note=f"licence {licence}",
                )
            )
        time.sleep(0.5)
    return out
