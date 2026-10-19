"""Parse the gnomAD v4.1 joint region subsets into one long frequency table."""

from __future__ import annotations

import gzip
from pathlib import Path

import polars as pl

from vwh.logs import get_logger

log = get_logger(__name__)


def _int(value: str | None) -> int | None:
    return None if value in (None, ".") else int(value)


def _float(value: str | None) -> float | None:
    return None if value in (None, ".") else float(value)


def parse_vcf(path: Path, groups: list[str]) -> pl.DataFrame:
    """One row per variant and ancestry group ('all' plus each group)."""
    rows: dict[str, list[object]] = {
        k: []
        for k in (
            "variant_key",
            "chrom",
            "pos",
            "ref",
            "alt",
            "ancestry_group",
            "ac",
            "an",
            "af",
            "nhomalt",
            "filter",
        )
    }
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            chrom, pos, _id, ref, alt, _q, filt, info = line.rstrip("\n").split("\t")[:8]
            if "," in alt:
                raise ValueError(f"{path.name}: multi-allelic record at {chrom}:{pos}")
            fields = dict(kv.split("=", 1) for kv in info.split(";") if "=" in kv)
            c = chrom.removeprefix("chr")
            key = f"{c}-{pos}-{ref}-{alt}"
            for grp in ["all", *groups]:
                sfx = "_joint" if grp == "all" else f"_joint_{grp}"
                an = _int(fields.get(f"AN{sfx}"))
                if an is None:
                    continue
                rows["variant_key"].append(key)
                rows["chrom"].append(c)
                rows["pos"].append(int(pos))
                rows["ref"].append(ref)
                rows["alt"].append(alt)
                rows["ancestry_group"].append(grp)
                rows["ac"].append(_int(fields.get(f"AC{sfx}")) or 0)
                rows["an"].append(an)
                rows["af"].append(_float(fields.get(f"AF{sfx}")))
                rows["nhomalt"].append(_int(fields.get(f"nhomalt{sfx}")))
                rows["filter"].append(filt)
    return pl.DataFrame(
        rows,
        schema={
            "variant_key": pl.String,
            "chrom": pl.String,
            "pos": pl.Int32,
            "ref": pl.String,
            "alt": pl.String,
            "ancestry_group": pl.String,
            "ac": pl.Int32,
            "an": pl.Int32,
            "af": pl.Float64,
            "nhomalt": pl.Int32,
            "filter": pl.String,
        },
    )


def stage(raw_dir: Path, staging_dir: Path, groups: list[str], release: str) -> int:
    frames = [parse_vcf(p, groups) for p in sorted(raw_dir.glob("gnomad.joint.v4.1.*.vcf.gz"))]
    df = pl.concat(frames).unique(subset=["variant_key", "ancestry_group"], keep="first")
    out = staging_dir / "gnomad" / release
    out.mkdir(parents=True, exist_ok=True)
    df.sort(["chrom", "pos", "variant_key", "ancestry_group"]).write_parquet(
        out / "frequencies.parquet"
    )
    log.info("staged gnomad", extra={"files": len(frames), "rows": df.height})
    return df.height
