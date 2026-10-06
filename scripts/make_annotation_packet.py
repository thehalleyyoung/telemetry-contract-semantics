#!/usr/bin/env python3
"""Build the blinded packet for an independent second annotator.

    python3 scripts/make_annotation_packet.py

Writes under docs/evaluation/annotation/:
  gold_blinded.jsonl      112 gold items: opaque id, bug class, definition, events
                          (no label, no rationale, no original id), shuffled
  gold_sheet.csv          one row per gold item: opaque_id, label (blank), confidence, note
  rq3_blinded.jsonl       60 RQ3 findings: opaque id, bug class, definition, repo,
                          file path, flagged message, event (no first-rater labels)
  rq3_sheet.csv           one row per finding: opaque_id + three blank label columns
  key.json                opaque id -> original id (annotators must not open this)
Ordering uses sha256(salt|id) with a fixed salt, so the packet is reproducible.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telemetry_contracts.bug_classes import BUG_CLASSES  # noqa: E402
from telemetry_contracts.evaluation.ground_truth import load_gold_set  # noqa: E402

OUT = ROOT / "docs" / "evaluation" / "annotation"
SALT = "telemetry-contracts-annotation-v1"


def opaque(prefix: str, ident: str) -> str:
    return f"{prefix}-{hashlib.sha256(f'{SALT}|{ident}'.encode()).hexdigest()[:10]}"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    key: dict[str, str] = {}

    gold = load_gold_set(str(ROOT / "benchmarks" / "ground_truth" / "curated.jsonl"))
    rows = []
    for item in gold:
        oid = opaque("G", item.id)
        key[oid] = item.id
        rows.append({
            "opaque_id": oid,
            "bug_class": item.bug_class,
            "definition": BUG_CLASSES[item.bug_class]["definition"],
            "events": item.events,
        })
    rows.sort(key=lambda r: r["opaque_id"])
    with (OUT / "gold_blinded.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    with (OUT / "gold_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["opaque_id", "bug_class", "label_present_yes_no", "confidence_1to3", "note"])
        for r in rows:
            w.writerow([r["opaque_id"], r["bug_class"], "", "", ""])

    sample = [json.loads(l) for l in (ROOT / "results" / "rq3" / "validation_sample.jsonl").read_text().splitlines() if l.strip()]
    rq = []
    for s in sample:
        oid = opaque("R", s["sample_id"])
        key[oid] = s["sample_id"]
        rq.append({
            "opaque_id": oid,
            "bug_class": s["bug_class"],
            "definition": BUG_CLASSES[s["bug_class"]]["definition"],
            "repository": f"https://github.com/{s['target']}/blob/{s['sha']}/{s['source_file']}"
            if not s["target"].startswith(("gl:", "bb:")) else f"{s['target']}@{s['sha']}:{s['source_file']}",
            "source_line": s["event_index"],
            "tool_message": s["message"],
            "event": s["event"],
        })
    rq.sort(key=lambda r: r["opaque_id"])
    with (OUT / "rq3_blinded.jsonl").open("w", encoding="utf-8") as fh:
        for r in rq:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    with (OUT / "rq3_sheet.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["opaque_id", "bug_class", "matches_definition", "artifact_kind",
                    "actionable_in_project_telemetry", "note"])
        for r in rq:
            w.writerow([r["opaque_id"], r["bug_class"], "", "", "", ""])
    (OUT / "key.json").write_text(json.dumps(dict(sorted(key.items())), indent=2) + "\n", encoding="utf-8")
    print(f"gold items: {len(rows)}; rq3 findings: {len(rq)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
