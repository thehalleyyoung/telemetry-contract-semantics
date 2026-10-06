#!/usr/bin/env python3
"""RQ3: dump every bug-class finding of the corpus study with its source event,
then draw a deterministic stratified sample for manual validation.

Prerequisite (network, once):
    python3 -m telemetry_contracts.cli corpus-download --manifest benchmarks/corpus/corpus.json

Usage:
    python3 scripts/rq3_extract_findings.py            # writes the two files below
    python3 scripts/rq3_extract_findings.py --per-class 15 --per-repo 2

Outputs:
    results/rq3/findings.jsonl          one line per finding (all bug classes)
    results/rq3/validation_sample.jsonl stratified sample (<= per-class per class,
                                        <= per-repo per (repo, class)), ordered by
                                        sha256(target|file|event_index|code)
The scan uses the same options as ``corpus-run`` (max_files=300,
max_events_per_file=50000), so finding counts match results/rq3/corpus_dataset.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telemetry_contracts.adapters import load_events_auto  # noqa: E402
from telemetry_contracts.bug_classes import CODE_TO_BUG_CLASS  # noqa: E402
from telemetry_contracts.mining.corpus import load_corpus_manifest  # noqa: E402
from telemetry_contracts.mining.runner import subject_checkout_dir  # noqa: E402
from telemetry_contracts.repo_scan import scan_directory  # noqa: E402

MAX_EVENT_CHARS = 1500


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="benchmarks/corpus/corpus.json")
    ap.add_argument("--repos-dir", default="benchmarks/corpus/_repos")
    ap.add_argument("--per-class", type=int, default=15)
    ap.add_argument("--per-repo", type=int, default=2)
    args = ap.parse_args()

    _protocol, subjects = load_corpus_manifest(str(ROOT / args.manifest))
    out_dir = ROOT / "results" / "rq3"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    # Note: analyze_events keeps at most 25 example findings per code per file,
    # so these counts (and the corpus dataset's) are lower bounds per file.
    for subject in subjects:
        checkout = subject_checkout_dir(ROOT / args.repos_dir, subject)
        if not checkout.exists():
            print(f"skip (not downloaded): {subject.target}", file=sys.stderr)
            continue
        report = scan_directory(checkout, max_files=300, max_events_per_file=50_000)
        cache: dict[str, list] = {}
        for f in report["findings"]:
            gap = CODE_TO_BUG_CLASS.get(f.get("code", ""))
            if gap is None:
                continue
            src = f.get("source_file")
            event = None
            idx = f.get("event_index")
            if src is not None and idx is not None:
                if src not in cache:
                    try:
                        cache[src] = load_events_auto(checkout / src, tolerant=True)["events"]
                    except Exception:  # noqa: BLE001 - record and continue
                        cache[src] = []
                # event_index is the event's source line (``_line``), not a list position.
                match = [e for e in cache[src] if e.get("_line") == idx]
                if match:
                    event = json.dumps(match[0], sort_keys=True, default=str)[:MAX_EVENT_CHARS]
            rows.append(
                {
                    "target": subject.target,
                    "sha": subject.sha,
                    "bug_class": gap,
                    "code": f["code"],
                    "severity": f.get("severity"),
                    "message": f.get("message"),
                    "path": f.get("path"),
                    "source_file": src,
                    "event_index": idx,
                    "event": event,
                }
            )
        print(f"{subject.target}: {sum(1 for r in rows if r['target'] == subject.target)} findings", file=sys.stderr)

    rows.sort(key=lambda r: (r["target"], r["bug_class"], str(r["source_file"]), r["event_index"] or -1, r["message"] or ""))
    with (out_dir / "findings.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

    def h(r: dict) -> str:
        key = f"{r['target']}|{r['source_file']}|{r['event_index']}|{r['code']}|{r['message']}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(rows, key=h):
        by_class[r["bug_class"]].append(r)
    sample: list[dict] = []
    for gap in sorted(by_class):
        per_repo: dict[str, int] = defaultdict(int)
        picked = 0
        for r in by_class[gap]:
            if picked >= args.per_class:
                break
            if per_repo[r["target"]] >= args.per_repo:
                continue
            per_repo[r["target"]] += 1
            picked += 1
            sample.append({"sample_id": f"rq3-{gap}-{picked:02d}", **r})
    with (out_dir / "validation_sample.jsonl").open("w", encoding="utf-8") as fh:
        for r in sample:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    counts = defaultdict(int)
    for r in rows:
        counts[r["bug_class"]] += 1
    print(json.dumps({"findings": len(rows), "by_class": dict(sorted(counts.items())), "sample": len(sample)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
