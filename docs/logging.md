# Logging

`vwh` writes one JSON object per line to stderr, and to a file with
`--log-file`. Every line has `ts` (local time with offset), `level`,
`logger` and `event`; the other keys depend on the event.

A load writes three kinds of line.

Before: one `input` line per source file (source, release, URL, path,
SHA-256) and a `load start` line with the target engine, the newest applied
migration and the migrations applied by this run.

During: a `step done` line per step of each ClinVar release with the seconds
spent, and a `clinvar loaded`, `gnomad loaded` or `mavedb loaded` line with
row counts.

After: a `load summary` line with status, total seconds, row counts per table
and the validation result. The same facts per file (URL, size, SHA-256,
fetch and load times, rows staged and loaded) go into the `provenance`
table inside the load transaction.

Excerpt from the full build on 2026-10-19 (`vwh --log-file load_all.jsonl
load all`), 2026-10 release:

```
{"ts": "2026-10-19T11:56:36-0700", "level": "info", "logger": "vwh.load", "event": "step done", "release": "2026-10", "step": "release", "seconds": 2.07}
{"ts": "2026-10-19T11:56:38-0700", "level": "info", "logger": "vwh.load", "event": "step done", "release": "2026-10", "step": "variant", "seconds": 2.51}
{"ts": "2026-10-19T11:56:41-0700", "level": "info", "logger": "vwh.load", "event": "step done", "release": "2026-10", "step": "clinvar_variation", "seconds": 2.69}
{"ts": "2026-10-19T11:56:45-0700", "level": "info", "logger": "vwh.load", "event": "step done", "release": "2026-10", "step": "classification_close", "seconds": 3.93}
{"ts": "2026-10-19T11:56:46-0700", "level": "info", "logger": "vwh.load", "event": "step done", "release": "2026-10", "step": "classification_open", "seconds": 1.42}
{"ts": "2026-10-19T11:56:53-0700", "level": "info", "logger": "vwh.load", "event": "step done", "release": "2026-10", "step": "submission", "seconds": 6.33}
{"ts": "2026-10-19T11:56:53-0700", "level": "info", "logger": "vwh.load", "event": "clinvar loaded", "release": "2026-10", "variations": 4575785, "submissions_staged": 6735012, "submissions_loaded": 6661309}
```

A rerun on the same database at 12:04 found every release recorded with the
same SHA-256 values and ended with:

```
{"ts": "2026-10-19T12:04:57-0700", "level": "info", "logger": "vwh", "event": "load start", "target": "duckdb", "schema_version": "0003_views.sql", "migrations_applied": [], "source": "all"}
{"ts": "2026-10-19T12:04:57-0700", "level": "info", "logger": "vwh.load", "event": "already loaded, skipping", "source": "clinvar", "release": "2026-10"}
{"ts": "2026-10-19T12:04:59-0700", "level": "info", "logger": "vwh", "event": "load summary", "status": "ok", "seconds": 1.7, "rows": {"source_release": 4, "provenance": 30, "gene": 20246, "variant": 4919816, "clinvar_variation": 4584619, "classification": 5416637, "submitter": 3580, "submission": 12257320, "population_frequency": 4243184, "score_set": 8, "functional_score": 71644}, "checks_passed": 18, "checks_failed": []}
```

The `input` lines and the `load start` and `load summary` events were added
after the full build, so they appear only in the rerun.

Errors: a failed transfer names the URL and curl's message; a staging error
names the file and the count of bad rows; a database error carries the
engine's message, which names the constraint and key (for example
`duplicate key "1, SCV000058352"`). `jq 'select(.level=="error")'` pulls them
out of a log file.
