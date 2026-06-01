#!/usr/bin/env python3
"""Regenerate the recorded-surrogate response cache for the baseline harness.

The cache is a deterministic, transparent **surrogate** policy used only to
exercise the offline LLM-baseline harness without network access. It is NOT an
LLM result and encodes no claim about real LLM accuracy (see
docs/evaluation/baselines.md). Run:

    python3 scripts/gen_llm_baseline_cache.py

to rewrite benchmarks/baselines/llm_recorded.json from the curated gold set.
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telemetry_contracts.evaluation.baselines import build_surrogate_cache  # noqa: E402
from telemetry_contracts.evaluation.ground_truth import load_gold_set  # noqa: E402

GOLD = ROOT / "benchmarks" / "ground_truth" / "curated.jsonl"
OUT = ROOT / "benchmarks" / "baselines" / "llm_recorded.json"


def main() -> int:
    items = load_gold_set(str(GOLD))
    cache = build_surrogate_cache(items)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(cache['responses'])} responses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
