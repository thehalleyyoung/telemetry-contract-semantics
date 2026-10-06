#!/usr/bin/env python3
"""Record a REAL LLM baseline on the curated gold set via OpenRouter.

For every gold item this sends the exact prompt produced by
``telemetry_contracts.evaluation.baselines.build_llm_prompt`` (the model sees
only the events and the bug-class definition, never the label or rationale),
records the raw response, and writes:

* ``results/llm_baseline/<slug>.raw.jsonl``   one line per call: item id, cache
  key, model requested, model served, prompt, raw response, usage, cost.
* ``benchmarks/baselines/llm_<slug>.json``    a ``telemetry-contracts/llm-recorded@1``
  cache the offline harness replays deterministically.
* ``results/api_costs.jsonl``                 appended: one line per call (model, cost).

Usage (requires OPENROUTER_API_KEY in the environment; network):

    python3 scripts/run_llm_baseline.py --model anthropic/claude-haiku-4.5
    python3 scripts/run_llm_baseline.py --model openai/gpt-4.1-mini

Decoding: temperature 0, max_tokens 200, one call per item, no retries on a
parseable answer. A response whose first token is not YES/NO is recorded as-is
and scored as NO (gap absent); the count of such responses is reported.
Re-running skips items already present in the raw file (resumable).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from telemetry_contracts.evaluation.baselines import (  # noqa: E402
    LLM_CACHE_SCHEMA,
    LLM_PROMPT_SCHEMA,
    build_llm_prompt,
    llm_cache_key,
    parse_llm_verdict,
)
from telemetry_contracts.evaluation.ground_truth import load_gold_set  # noqa: E402

GOLD = ROOT / "benchmarks" / "ground_truth" / "curated.jsonl"
URL = "https://openrouter.ai/api/v1/chat/completions"
BUDGET_USD = 5.0


def slug(model: str) -> str:
    return model.replace("/", "__").replace(":", "_").replace(".", "-")


def total_spend(path: pathlib.Path) -> float:
    if not path.exists():
        return 0.0
    total = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            total += float(json.loads(line).get("cost_usd") or 0.0)
    return total


def call(model: str, prompt: str, key: str) -> dict:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 200,
            "usage": {"include": True},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        URL,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:  # transient network
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
            print(f"retry after {exc}", file=sys.stderr)
    raise RuntimeError("unreachable")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--gold", default=str(GOLD))
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("OPENROUTER_API_KEY not set", file=sys.stderr)
        return 2

    items = load_gold_set(args.gold)
    s = slug(args.model)
    raw_path = ROOT / "results" / "llm_baseline" / f"{s}.raw.jsonl"
    cost_path = ROOT / "results" / "api_costs.jsonl"
    cache_path = ROOT / "benchmarks" / "baselines" / f"llm_{s}.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    done: dict[str, dict] = {}
    if raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["id"]] = rec

    for item in items:
        if item.id in done:
            continue
        if total_spend(cost_path) >= BUDGET_USD:
            print("budget cap reached; stopping", file=sys.stderr)
            return 3
        prompt = build_llm_prompt(item.events, item.bug_class)
        resp = call(args.model, prompt, key)
        if "choices" not in resp:
            print(f"API error on {item.id}: {json.dumps(resp)[:300]}", file=sys.stderr)
            return 4
        text = resp["choices"][0]["message"].get("content") or ""
        usage = resp.get("usage", {})
        cost = float(usage.get("cost") or 0.0)
        rec = {
            "id": item.id,
            "bug_class": item.bug_class,
            "cache_key": llm_cache_key(item.events, item.bug_class),
            "model_requested": args.model,
            "model_served": resp.get("model"),
            "provider": resp.get("provider"),
            "generation_id": resp.get("id"),
            "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "decoding": {"temperature": 0, "max_tokens": 200},
            "prompt": prompt,
            "response": text,
            "usage": usage,
        }
        with raw_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        with cost_path.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "purpose": "llm-baseline gold set",
                        "model": args.model,
                        "model_served": resp.get("model"),
                        "item": item.id,
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "cost_usd": cost,
                        "timestamp_utc": rec["timestamp_utc"],
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        done[item.id] = rec
        print(f"{item.id}: {text.strip().splitlines()[0] if text.strip() else '<empty>'}")

    # Build the replay cache (verdict parsed from the raw response).
    responses: dict[str, dict] = {}
    unparseable = 0
    for item in items:
        rec = done[item.id]
        try:
            verdict = "YES" if parse_llm_verdict(rec["response"]) else "NO"
            parse_ok = True
        except ValueError:
            verdict, parse_ok = "NO", False
            unparseable += 1
        responses[rec["cache_key"]] = {
            "verdict": verdict,
            "parse_ok": parse_ok,
            "raw_response": rec["response"],
        }
    served = sorted({str(r.get("model_served")) for r in done.values()})
    cache = {
        "schema": LLM_CACHE_SCHEMA,
        "prompt_schema": LLM_PROMPT_SCHEMA,
        "policy": "Real LLM responses recorded via OpenRouter (see raw_log).",
        "model": args.model,
        "model_served": served,
        "decoding": {"temperature": 0, "max_tokens": 200},
        "raw_log": str(raw_path.relative_to(ROOT)),
        "unparseable_scored_as_no": unparseable,
        "responses": dict(sorted(responses.items())),
    }
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    spent = sum(
        float((r.get("usage") or {}).get("cost") or 0.0) for r in done.values()
    )
    print(f"wrote {cache_path.relative_to(ROOT)}; unparseable={unparseable}; model cost=${spent:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
