"""Mechanics of the second-annotator agreement script (no human labels involved).

The test fills a copy of the blank sheet programmatically to check the
plumbing (key lookup, kappa arithmetic, blank handling). It is not, and must
never be reported as, an agreement measurement.
"""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("annotation_agreement", ROOT / "scripts" / "annotation_agreement.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_kappa_known_values():
    assert mod.cohen_kappa(["yes", "no", "yes", "no"], ["yes", "no", "yes", "no"]) == 1.0
    assert abs(mod.cohen_kappa(["yes", "yes", "no", "no"], ["yes", "no", "yes", "no"])) < 1e-12
    assert mod.cohen_kappa([], []) is None


def test_packet_is_blinded_and_complete():
    ann = ROOT / "docs" / "evaluation" / "annotation"
    rows = [json.loads(l) for l in (ann / "gold_blinded.jsonl").read_text().splitlines()]
    assert len(rows) == 112
    for r in rows:
        assert set(r) == {"opaque_id", "bug_class", "definition", "events"}
    rq = [json.loads(l) for l in (ann / "rq3_blinded.jsonl").read_text().splitlines()]
    assert len(rq) == 60 and all("matches_definition" not in r for r in rq)


def test_gold_plumbing_with_mechanical_fill(tmp_path):
    ann = ROOT / "docs" / "evaluation" / "annotation"
    key = json.loads((ann / "key.json").read_text())
    from telemetry_contracts.evaluation.ground_truth import load_gold_set
    labels = {i.id: i.label for i in load_gold_set(str(ROOT / "benchmarks" / "ground_truth" / "curated.jsonl"))}
    src = list(csv.DictReader((ann / "gold_sheet.csv").open()))
    out = tmp_path / "sheet.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(src[0]))
        w.writeheader()
        for n, row in enumerate(src):
            if n == 0:
                w.writerow(row)  # left blank -> skipped
                continue
            row["label_present_yes_no"] = "yes" if labels[key[row["opaque_id"]]] else "no"
            w.writerow(row)
    res = mod.gold_agreement(out)
    assert res["n_compared"] == 111 and res["n_blank_skipped"] == 1
    assert res["cohen_kappa"] == 1.0 and res["disagreements"] == []
