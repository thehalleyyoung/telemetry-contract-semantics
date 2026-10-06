#!/usr/bin/env python3
"""Summarise the RQ3 validation labels (results/rq3/validation_labels.csv)
joined with the sample (results/rq3/validation_sample.jsonl).

    python3 scripts/rq3_validation_summary.py  ->  results/rq3/validation_summary.json

Labels were assigned by LLM-assisted inspection (the coordinating agent read
each flagged event in the pinned checkout); they are NOT human expert labels.
"""
from __future__ import annotations

import csv
import json
import pathlib
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
D = ROOT / "results" / "rq3"

sample = {json.loads(l)["sample_id"]: json.loads(l) for l in (D / "validation_sample.jsonl").read_text().splitlines() if l.strip()}
labels = list(csv.DictReader((D / "validation_labels.csv").open(encoding="utf-8")))
assert {r["sample_id"] for r in labels} == set(sample), "labels and sample differ"

by_class: dict[str, Counter] = defaultdict(Counter)
overall: Counter = Counter()
artifacts: Counter = Counter()
for r in labels:
    gap = sample[r["sample_id"]]["bug_class"]
    by_class[gap]["n"] += 1
    by_class[gap]["def_" + r["matches_definition"]] += 1
    by_class[gap]["actionable_" + r["actionable_in_project_telemetry"]] += 1
    overall["n"] += 1
    overall["def_" + r["matches_definition"]] += 1
    overall["actionable_" + r["actionable_in_project_telemetry"]] += 1
    artifacts[r["artifact_kind"]] += 1


def rates(c: Counter) -> dict:
    n = c["n"]
    return {
        **dict(sorted(c.items())),
        "precision_strict": round(c["def_yes"] / n, 3),
        "precision_lenient_borderline_as_yes": round((c["def_yes"] + c["def_borderline"]) / n, 3),
        "actionable_share": round(c["actionable_yes"] / n, 3),
    }


out = {
    "method": "LLM-assisted inspection of each sampled finding's source event in the pinned checkout; single rater; not human expert review",
    "sample": "stratified: <=15 findings per bug class, <=2 per (repo, class), ordered by sha256 (scripts/rq3_extract_findings.py)",
    "overall": rates(overall),
    "by_class": {k: rates(v) for k, v in sorted(by_class.items())},
    "artifact_kind": dict(sorted(artifacts.items())),
}
(D / "validation_summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
