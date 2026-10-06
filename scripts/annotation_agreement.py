#!/usr/bin/env python3
"""Agreement between the first rater and an independent second annotator.

    python3 scripts/annotation_agreement.py --gold-sheet filled_gold_sheet.csv \
        [--rq3-sheet filled_rq3_sheet.csv] [--out results/annotation_agreement.json]

Gold: compares the annotator's yes/no to the primary label in
benchmarks/ground_truth/curated.jsonl (Cohen's kappa, raw agreement, 2x2 table,
95% bootstrap CI for kappa with a fixed seed) and re-scores the tool on the
subset where both raters agree.
RQ3: compares each of the three label columns to results/rq3/validation_labels.csv
(Cohen's kappa for matches_definition yes/no/borderline and the other columns).
Blank rows are skipped and counted. Pure stdlib.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import random
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telemetry_contracts.evaluation.ground_truth import load_gold_set  # noqa: E402
from telemetry_contracts.evaluation.scorer import predict_bug_class  # noqa: E402

ANN = ROOT / "docs" / "evaluation" / "annotation"


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    cats = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def bootstrap_ci(a: list[str], b: list[str], reps: int = 2000, seed: int = 7) -> list[float] | None:
    if len(a) < 2:
        return None
    rng = random.Random(seed)
    idx = range(len(a))
    vals = []
    for _ in range(reps):
        s = [rng.choice(idx) for _ in idx]
        k = cohen_kappa([a[i] for i in s], [b[i] for i in s])
        if k is not None:
            vals.append(k)
    if not vals:
        return None
    vals.sort()
    return [round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals)) - 1], 3)]


def norm_yes_no(v: str) -> str | None:
    v = (v or "").strip().lower()
    if v in {"yes", "y", "true", "1", "present"}:
        return "yes"
    if v in {"no", "n", "false", "0", "absent"}:
        return "no"
    return None


def gold_agreement(sheet: pathlib.Path) -> dict:
    key = json.loads((ANN / "key.json").read_text(encoding="utf-8"))
    items = {i.id: i for i in load_gold_set(str(ROOT / "benchmarks" / "ground_truth" / "curated.jsonl"))}
    a, b, ids, skipped = [], [], [], 0
    for row in csv.DictReader(sheet.open(encoding="utf-8")):
        lab = norm_yes_no(row.get("label_present_yes_no", ""))
        if lab is None:
            skipped += 1
            continue
        item = items[key[row["opaque_id"]]]
        a.append("yes" if item.label else "no")
        b.append(lab)
        ids.append(item.id)
    table = Counter(zip(a, b))
    agreed = [i for i, x, y in zip(ids, a, b) if x == y]
    tp = fp = fn = tn = 0
    for i in agreed:
        it = items[i]
        pred, _ = predict_bug_class(it.events, it.bug_class)
        if it.label and pred:
            tp += 1
        elif it.label:
            fn += 1
        elif pred:
            fp += 1
        else:
            tn += 1
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * p * r / (p + r) if p and r else None
    k = cohen_kappa(a, b)
    return {
        "n_compared": len(a),
        "n_blank_skipped": skipped,
        "raw_agreement": round(sum(x == y for x, y in zip(a, b)) / len(a), 3) if a else None,
        "cohen_kappa": round(k, 3) if k is not None else None,
        "kappa_95ci_bootstrap": bootstrap_ci(a, b),
        "table_primary_vs_second": {f"{x}/{y}": c for (x, y), c in sorted(table.items())},
        "disagreements": sorted(i for i, x, y in zip(ids, a, b) if x != y),
        "tool_on_agreed_subset": {"n": len(agreed), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                                  "precision": p and round(p, 3), "recall": r and round(r, 3),
                                  "f1": f1 and round(f1, 3)},
    }


def rq3_agreement(sheet: pathlib.Path) -> dict:
    key = json.loads((ANN / "key.json").read_text(encoding="utf-8"))
    first = {r["sample_id"]: r for r in csv.DictReader((ROOT / "results" / "rq3" / "validation_labels.csv").open(encoding="utf-8"))}
    out = {}
    rows = list(csv.DictReader(sheet.open(encoding="utf-8")))
    for col in ("matches_definition", "artifact_kind", "actionable_in_project_telemetry"):
        a, b = [], []
        for row in rows:
            v = (row.get(col) or "").strip().lower()
            if not v:
                continue
            a.append(first[key[row["opaque_id"]]][col])
            b.append(v)
        k = cohen_kappa(a, b)
        out[col] = {"n_compared": len(a),
                    "raw_agreement": round(sum(x == y for x, y in zip(a, b)) / len(a), 3) if a else None,
                    "cohen_kappa": round(k, 3) if k is not None else None,
                    "kappa_95ci_bootstrap": bootstrap_ci(a, b)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-sheet", type=pathlib.Path)
    ap.add_argument("--rq3-sheet", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args()
    res: dict = {}
    if args.gold_sheet:
        res["gold"] = gold_agreement(args.gold_sheet)
    if args.rq3_sheet:
        res["rq3"] = rq3_agreement(args.rq3_sheet)
    text = json.dumps(res, indent=2, sort_keys=True)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
