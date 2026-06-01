"""Deterministic comparison baselines for the observability bug-class detectors.

ICSE reviewers reject papers without baselines. This module ships three
*runnable, offline, byte-deterministic* comparators scored through the exact
same gold-set pipeline as the tool (:func:`telemetry_contracts.evaluation.score_gold_set`),
plus a head-to-head comparison with a paired significance test, a symmetric
win/loss analysis, and a cost/feasibility table.

The comparators are **capability baselines**, deliberately scoped, not claimed
state-of-the-art detectors:

* ``rule-light`` — a deliberately naive field-NAME keyword detector (no
  thresholds, no statistics, no failure gating, no value inspection). It is the
  lower-bound sanity baseline: "what if we only checked obvious field names?".
* ``semantic-convention-only`` — flags solely missing OpenTelemetry-convention
  fields. It is intentionally limited to the bug classes expressible as a
  convention field; the other classes are reported **out of scope** (a coverage
  result, not an accuracy penalty). It tests the claim that *convention
  conformance is not the same as correctness*.
* ``recorded-surrogate`` — a deterministic prompt + parser + cache *harness*
  intended to host an LLM-only comparator offline. Because the artifact ships no
  network and no commercial-model output, the cache contains a **transparent,
  hand-written surrogate policy** (a high-recall over-flagging reviewer). It is
  **not** an LLM result and makes **no** claim about real LLM accuracy; it exists
  to (1) prove the harness is deterministic + offline and (2) provide a
  comparator with a different (over-flagging) error profile.

All baselines see only ``(events, bug_class)`` — never the gold label or
rationale. Their definitions are frozen before the comparison is snapshotted and
no threshold is tuned on the gold set.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from math import comb
from typing import Any

from ..bug_classes import BUG_CLASS_IDS, BUG_CLASSES
from .ground_truth import GoldItem
from .scorer import (
    Predictor,
    _class_metrics,
    _fmt_permille,
    _macro_average,
    predict_bug_class,
)

BASELINES_SCHEMA = "telemetry-contracts/baselines@1"

# --- failure / field helpers ------------------------------------------------

_FAILURE_SEVERITIES = {"error", "critical", "fatal", "warning", "warn"}
_FAILURE_VALUES = {"error", "failed", "failure", "fail", "ko", "timeout", "timedout"}


def _field_names(events: list[dict[str, Any]]) -> set[str]:
    """Lower-cased top-level field names present across ``events`` (deterministic)."""

    names: set[str] = set()
    for event in events:
        if isinstance(event, dict):
            for key in event:
                names.add(str(key).strip().lower())
    return names


def _has_any_name(events: list[dict[str, Any]], wanted: tuple[str, ...]) -> bool:
    names = _field_names(events)
    return any(w in names for w in wanted)


def _name_contains_any(events: list[dict[str, Any]], needles: tuple[str, ...]) -> bool:
    names = _field_names(events)
    return any(any(n in name for n in needles) for name in names)


def _looks_failureish(events: list[dict[str, Any]]) -> bool:
    for event in events:
        if not isinstance(event, dict):
            continue
        severity = event.get("severity")
        if isinstance(severity, str) and severity.strip().lower() in _FAILURE_SEVERITIES:
            return True
        for key in ("status", "outcome", "result", "level"):
            value = event.get(key)
            if isinstance(value, str) and value.strip().lower() in _FAILURE_VALUES:
                return True
    return False


def _witness(method: str, bug_class: str, present: bool) -> list[str]:
    """Predictor-specific witness label (NOT a shipped finding code)."""

    if not present:
        return []
    return [f"baseline.{method}.{bug_class.replace('-', '_')}"]


# --- baseline 1: rule-light --------------------------------------------------

_RL_CORRELATION = ("trace_id", "span_id", "request_id", "correlation_id")
_RL_DURATION = ("duration", "duration_ms", "duration_ns", "elapsed", "latency_ms")
_RL_ERROR_EVIDENCE = (
    "error_code",
    "error",
    "errorcode",
    "exception",
    "exception_type",
    "stack",
    "stack_trace",
    "stacktrace",
    "status",
    "status_code",
    "error_message",
)
_RL_SENSITIVE_VALUE_NAMES = ("password", "token", "secret", "ssn", "credit_card", "api_key")
_RL_UNCLASSIFIED_NAMES = (
    "user_id",
    "org_id",
    "account_id",
    "customer_id",
    "tenant_id",
    "session_id",
    "email",
    "phone",
)


def predict_rule_light(events: list[dict[str, Any]], bug_class: str) -> tuple[bool, list[str]]:
    """Deliberately naive field-name keyword detector (lower-bound baseline)."""

    if bug_class == "missing-correlation":
        present = not _has_any_name(events, _RL_CORRELATION)
    elif bug_class == "missing-duration":
        present = not _has_any_name(events, _RL_DURATION)
    elif bug_class == "missing-error-evidence":
        present = not _has_any_name(events, _RL_ERROR_EVIDENCE)
    elif bug_class == "sensitive-values":
        present = _name_contains_any(events, _RL_SENSITIVE_VALUE_NAMES)
    elif bug_class == "unclassified-sensitive":
        present = _name_contains_any(events, _RL_UNCLASSIFIED_NAMES)
    else:  # unbounded-cardinality: rule-light has no statistical notion.
        present = False
    return present, _witness("rule_light", bug_class, present)


# --- baseline 2: semantic-convention-only -----------------------------------

_SC_TRACE_CONTEXT = ("trace_id", "span_id")
_SC_DURATION = ("duration", "duration_ms", "duration_ns")
_SC_ERROR = (
    "exception.type",
    "exception.message",
    "exception.stacktrace",
    "exception_type",
    "exception_message",
    "otel.status_code",
    "status",
    "error",
)
SC_COVERED_CLASSES = (
    "missing-correlation",
    "missing-duration",
    "missing-error-evidence",
)


def predict_semantic_convention_only(
    events: list[dict[str, Any]], bug_class: str
) -> tuple[bool, list[str]]:
    """Flag solely missing OpenTelemetry-convention fields (coverage-limited)."""

    if bug_class == "missing-correlation":
        present = not _has_any_name(events, _SC_TRACE_CONTEXT)
    elif bug_class == "missing-duration":
        present = not _has_any_name(events, _SC_DURATION)
    elif bug_class == "missing-error-evidence":
        present = not _has_any_name(events, _SC_ERROR)
    else:
        # OTel semantic conventions do not define a detector for sensitive
        # values, unclassified identifiers, or unbounded cardinality.
        present = False
    return present, _witness("semantic_convention", bug_class, present)


# --- baseline 3: recorded-surrogate (LLM harness) ---------------------------

LLM_PROMPT_SCHEMA = "telemetry-contracts/llm-baseline-prompt@1"
LLM_CACHE_SCHEMA = "telemetry-contracts/llm-recorded@1"


def build_llm_prompt(events: list[dict[str, Any]], bug_class: str) -> str:
    """Build the deterministic LLM-baseline prompt for one (events, class) item."""

    definition = BUG_CLASSES[bug_class]["definition"]
    body = json.dumps(events, sort_keys=True, separators=(",", ":"))
    return (
        f"[{LLM_PROMPT_SCHEMA}] You are auditing telemetry for missing observability.\n"
        f"Bug class: {bug_class}\n"
        f"Definition: {definition}\n"
        f"Events (JSON): {body}\n"
        "Does this telemetry exhibit the bug class? Answer strictly YES or NO on "
        "the first line, then a one-sentence rationale."
    )


def parse_llm_verdict(response: str) -> bool:
    """Parse a YES/NO verdict from a recorded response's first token."""

    if not isinstance(response, str):
        raise ValueError("llm response must be a string")
    head = response.strip().splitlines()[0].strip().upper() if response.strip() else ""
    token = head.split()[0] if head else ""
    token = token.strip(".:,!").upper()
    if token in {"YES", "Y", "TRUE", "GAP", "PRESENT"}:
        return True
    if token in {"NO", "N", "FALSE", "OK", "ABSENT"}:
        return False
    raise ValueError(f"unparseable llm verdict: {response!r}")


def llm_cache_key(events: list[dict[str, Any]], bug_class: str) -> str:
    """Stable cache key (sha256 of canonical events + bug class)."""

    payload = json.dumps(
        {"bug_class": bug_class, "events": events},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def surrogate_verdict(events: list[dict[str, Any]], bug_class: str) -> tuple[bool, str]:
    """The transparent surrogate policy that fills the recorded cache.

    A deliberately high-recall, low-precision "optimistic reviewer": it answers
    YES (gap present) whenever the class's targeted field family is entirely
    absent OR the events carry any failure/anomaly cue. This is NOT an LLM and
    encodes no claim about real LLM behaviour; it only provides a deterministic
    comparator with a different (over-flagging) error profile.
    """

    family = {
        "missing-correlation": _RL_CORRELATION,
        "missing-duration": _RL_DURATION,
        "missing-error-evidence": _RL_ERROR_EVIDENCE,
        "sensitive-values": _RL_SENSITIVE_VALUE_NAMES,
        "unclassified-sensitive": _RL_UNCLASSIFIED_NAMES,
        "unbounded-cardinality": ("value", "label", "labels", "tags"),
    }[bug_class]
    family_absent = not _name_contains_any(events, family)
    anomaly = _looks_failureish(events)
    present = family_absent or anomaly
    reason = []
    if family_absent:
        reason.append("targeted field family appears absent")
    if anomaly:
        reason.append("events carry a failure/anomaly cue")
    rationale = "; ".join(reason) if reason else "no cue observed"
    return present, rationale


def build_surrogate_cache(items: list[GoldItem]) -> dict[str, Any]:
    """Build the recorded-surrogate response cache for a gold set (deterministic)."""

    responses: dict[str, dict[str, str]] = {}
    for item in items:
        key = llm_cache_key(item.events, item.bug_class)
        verdict, rationale = surrogate_verdict(item.events, item.bug_class)
        responses[key] = {
            "verdict": "YES" if verdict else "NO",
            "rationale": rationale,
        }
    return {
        "schema": LLM_CACHE_SCHEMA,
        "policy": (
            "Transparent hand-written surrogate (high-recall over-flagging "
            "reviewer). NOT an LLM and not evidence of LLM accuracy; provided to "
            "exercise the offline harness with a different error profile."
        ),
        "prompt_schema": LLM_PROMPT_SCHEMA,
        "responses": dict(sorted(responses.items())),
    }


def make_recorded_surrogate_predictor(cache: dict[str, Any]) -> Predictor:
    """Build a predictor that replays a recorded response cache through the harness."""

    responses = cache.get("responses", {})

    def predict(events: list[dict[str, Any]], bug_class: str) -> tuple[bool, list[str]]:
        key = llm_cache_key(events, bug_class)
        if key not in responses:
            raise KeyError(
                f"recorded-surrogate cache miss for {bug_class} (key {key[:12]}…); "
                "regenerate the cache with scripts/gen_llm_baseline_cache.py"
            )
        present = parse_llm_verdict(responses[key]["verdict"])
        return present, _witness("recorded_surrogate", bug_class, present)

    return predict


# --- method registry --------------------------------------------------------


def _method_specs() -> list[dict[str, Any]]:
    """Static, frozen description of each method (the tool + baselines)."""

    return [
        {
            "id": "tool",
            "name": "telemetry-contracts (this tool)",
            "kind": "tool",
            "covered_classes": list(BUG_CLASS_IDS),
            "description": "The shipped zero-config detectors (value-aware, "
            "failure-gated, statistical cardinality).",
            "feasibility": {
                "setup_required": "none (point at telemetry you already have)",
                "conventions_assumed": "none",
                "deterministic": True,
                "offline": True,
                "value_aware": True,
                "statistical": True,
            },
        },
        {
            "id": "rule-light",
            "name": "rule-light keyword detector",
            "kind": "baseline",
            "covered_classes": [c for c in BUG_CLASS_IDS if c != "unbounded-cardinality"],
            "description": "Deliberately naive field-NAME keyword presence only; "
            "no thresholds, statistics, failure gating, or value inspection.",
            "feasibility": {
                "setup_required": "none",
                "conventions_assumed": "none",
                "deterministic": True,
                "offline": True,
                "value_aware": False,
                "statistical": False,
            },
        },
        {
            "id": "semantic-convention-only",
            "name": "OTel semantic-convention conformance",
            "kind": "baseline",
            "covered_classes": list(SC_COVERED_CLASSES),
            "description": "Flags solely missing OpenTelemetry-convention fields; "
            "classes with no convention field are out of scope (coverage result).",
            "feasibility": {
                "setup_required": "adopt OTel semantic conventions",
                "conventions_assumed": "OpenTelemetry",
                "deterministic": True,
                "offline": True,
                "value_aware": False,
                "statistical": False,
            },
        },
        {
            "id": "recorded-surrogate",
            "name": "recorded-surrogate (LLM harness check)",
            "kind": "surrogate",
            "covered_classes": list(BUG_CLASS_IDS),
            "description": "Deterministic prompt+parser+cache harness replaying a "
            "transparent hand-written surrogate policy. NOT an LLM result.",
            "feasibility": {
                "setup_required": "model access (real LLM) — surrogate shipped offline",
                "conventions_assumed": "none",
                "deterministic": True,
                "offline": True,
                "value_aware": False,
                "statistical": False,
            },
        },
    ]


# --- paired McNemar exact test ---------------------------------------------


def _mcnemar_exact(b: int, c: int) -> dict[str, Any]:
    """Exact two-sided McNemar/sign test over discordant pairs (deterministic).

    ``b`` = items the tool gets right but the baseline gets wrong; ``c`` = the
    reverse. Returns the discordant counts and an exact two-sided p-value
    rendered in ten-thousandths (half-up), plus a 0.05-significance flag.
    """

    n = b + c
    if n == 0:
        p = Fraction(1)
    else:
        k = min(b, c)
        tail = sum(comb(n, i) for i in range(0, k + 1))
        p = min(Fraction(1), Fraction(2 * tail, 2 ** n))
    p_ten_thousandths = (p.numerator * 10000 + p.denominator // 2) // p.denominator
    return {
        "discordant_tool_only": b,
        "discordant_baseline_only": c,
        "discordant_total": n,
        "two_sided_exact_p_ten_thousandths": p_ten_thousandths,
        "significant_at_0p05": p <= Fraction(5, 100),
    }


# --- comparison -------------------------------------------------------------


def _score_one(items: list[GoldItem], predict: Predictor, covered: list[str]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {
        gap: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for gap in BUG_CLASS_IDS
    }
    correct: dict[str, bool] = {}
    for item in items:
        predicted, _codes = predict(item.events, item.bug_class)
        bucket = counts[item.bug_class]
        if item.label and predicted:
            bucket["tp"] += 1
        elif item.label and not predicted:
            bucket["fn"] += 1
        elif not item.label and predicted:
            bucket["fp"] += 1
        else:
            bucket["tn"] += 1
        correct[item.id] = predicted == item.label

    per_class = {gap: _class_metrics(**counts[gap]) for gap in BUG_CLASS_IDS}
    tp = sum(c["tp"] for c in counts.values())
    fp = sum(c["fp"] for c in counts.values())
    fn = sum(c["fn"] for c in counts.values())
    tn = sum(c["tn"] for c in counts.values())
    overall = _class_metrics(tp, fp, fn, tn)
    overall["predicted_positive"] = tp + fp

    covered_set = set(covered)
    cc = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for gap in covered:
        for k in cc:
            cc[k] += counts[gap][k]
    covered_metrics = _class_metrics(**cc)
    covered_metrics["predicted_positive"] = cc["tp"] + cc["fp"]

    macro = {
        "precision_permille": _macro_average([per_class[g]["precision_permille"] for g in BUG_CLASS_IDS]),
        "recall_permille": _macro_average([per_class[g]["recall_permille"] for g in BUG_CLASS_IDS]),
        "f1_permille": _macro_average([per_class[g]["f1_permille"] for g in BUG_CLASS_IDS]),
    }
    return {
        "overall": overall,
        "macro": macro,
        "covered": covered_metrics,
        "per_class_f1_permille": {g: per_class[g]["f1_permille"] for g in BUG_CLASS_IDS},
        "_correct": correct,
        "out_of_scope_classes": sorted(set(BUG_CLASS_IDS) - covered_set),
    }


def _win_loss(
    items: list[GoldItem], tool_correct: dict[str, bool], base_correct: dict[str, bool]
) -> dict[str, list[str]]:
    tool_only: list[str] = []
    baseline_only: list[str] = []
    shared_fp: list[str] = []
    shared_fn: list[str] = []
    for item in items:
        tc = tool_correct[item.id]
        bc = base_correct[item.id]
        if tc and not bc:
            tool_only.append(item.id)
        elif bc and not tc:
            baseline_only.append(item.id)
        elif not tc and not bc:
            # both wrong: classify by the gold label (both FP vs both FN).
            (shared_fn if item.label else shared_fp).append(item.id)
    return {
        "tool_only_correct": sorted(tool_only),
        "baseline_only_correct": sorted(baseline_only),
        "shared_false_negative": sorted(shared_fn),
        "shared_false_positive": sorted(shared_fp),
    }


def compare_baselines(
    items: list[GoldItem], recorded_cache: dict[str, Any]
) -> dict[str, Any]:
    """Run the tool + every baseline over ``items`` and build the comparison."""

    predictors: dict[str, Predictor] = {
        "tool": predict_bug_class,
        "rule-light": predict_rule_light,
        "semantic-convention-only": predict_semantic_convention_only,
        "recorded-surrogate": make_recorded_surrogate_predictor(recorded_cache),
    }

    specs = _method_specs()
    scored: dict[str, dict[str, Any]] = {}
    for spec in specs:
        scored[spec["id"]] = _score_one(items, predictors[spec["id"]], spec["covered_classes"])

    tool_correct = scored["tool"]["_correct"]

    methods: list[dict[str, Any]] = []
    for spec in specs:
        sid = spec["id"]
        s = scored[sid]
        method: dict[str, Any] = {
            "id": sid,
            "name": spec["name"],
            "kind": spec["kind"],
            "description": spec["description"],
            "covered_classes": list(spec["covered_classes"]),
            "out_of_scope_classes": s["out_of_scope_classes"],
            "overall": s["overall"],
            "macro": s["macro"],
            "covered": s["covered"],
            "per_class_f1_permille": s["per_class_f1_permille"],
            "feasibility": spec["feasibility"],
        }
        if sid != "tool":
            wl = _win_loss(items, tool_correct, s["_correct"])
            mc = _mcnemar_exact(len(wl["tool_only_correct"]), len(wl["baseline_only_correct"]))
            method["vs_tool"] = {**wl, "mcnemar": mc}
        else:
            method["vs_tool"] = None
        methods.append(method)

    return {
        "schema": BASELINES_SCHEMA,
        "gold_samples": len(items),
        "frozen_note": (
            "Baseline definitions are fixed before snapshotting; no threshold is "
            "tuned on the gold set; every method sees only (events, bug_class), "
            "never the gold label or rationale. Out-of-scope classes are reported "
            "as coverage gaps, not accuracy failures."
        ),
        "methods": methods,
    }


def render_baselines_markdown(comparison: dict[str, Any]) -> str:
    methods = comparison["methods"]
    lines = [
        "# Baseline comparison (head-to-head on the curated gold set)",
        "",
        f"All methods scored on the same **{comparison['gold_samples']}** hand-labeled "
        "samples, through the identical pipeline. Metrics describe this curated, "
        "balanced set (not a prevalence-representative sample).",
        "",
        "> " + comparison["frozen_note"],
        "",
        "## All-class (micro-averaged)",
        "",
        "| Method | Kind | Precision | Recall | F1 | Macro F1 | Predicted+ | TP/FP/FN/TN |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for m in methods:
        o = m["overall"]
        lines.append(
            f"| {m['name']} | {m['kind']} | {_fmt_permille(o['precision_permille'])} | "
            f"{_fmt_permille(o['recall_permille'])} | {_fmt_permille(o['f1_permille'])} | "
            f"{_fmt_permille(m['macro']['f1_permille'])} | {o['predicted_positive']} | "
            f"{o['tp']}/{o['fp']}/{o['fn']}/{o['tn']} |"
        )
    lines += [
        "",
        "## Covered-class only (excludes each method's out-of-scope classes)",
        "",
        "| Method | Covered classes | Precision | Recall | F1 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for m in methods:
        cov = m["covered"]
        n_cov = len(m["covered_classes"])
        lines.append(
            f"| {m['name']} | {n_cov}/{len(comparison['methods'][0]['covered_classes'])} | "
            f"{_fmt_permille(cov['precision_permille'])} | "
            f"{_fmt_permille(cov['recall_permille'])} | "
            f"{_fmt_permille(cov['f1_permille'])} |"
        )
    lines += [
        "",
        "## Paired significance vs the tool (exact two-sided McNemar)",
        "",
        "| Baseline | Tool-only correct | Baseline-only correct | Exact p | Sig. @0.05 |",
        "| --- | ---: | ---: | ---: | :---: |",
    ]
    for m in methods:
        if m["vs_tool"] is None:
            continue
        mc = m["vs_tool"]["mcnemar"]
        p = mc["two_sided_exact_p_ten_thousandths"] / 10000
        lines.append(
            f"| {m['name']} | {mc['discordant_tool_only']} | "
            f"{mc['discordant_baseline_only']} | {p:.4f} | "
            f"{'yes' if mc['significant_at_0p05'] else 'no'} |"
        )
    lines += [
        "",
        "## Symmetric win/loss vs the tool",
        "",
    ]
    for m in methods:
        if m["vs_tool"] is None:
            continue
        wl = m["vs_tool"]
        lines += [
            f"### {m['name']}",
            "",
            f"- Tool-only correct ({len(wl['tool_only_correct'])}): "
            f"{', '.join('`'+i+'`' for i in wl['tool_only_correct']) or '—'}",
            f"- Baseline-only correct ({len(wl['baseline_only_correct'])}): "
            f"{', '.join('`'+i+'`' for i in wl['baseline_only_correct']) or '—'}",
            f"- Shared false negatives ({len(wl['shared_false_negative'])}): "
            f"{', '.join('`'+i+'`' for i in wl['shared_false_negative']) or '—'}",
            f"- Shared false positives ({len(wl['shared_false_positive'])}): "
            f"{', '.join('`'+i+'`' for i in wl['shared_false_positive']) or '—'}",
            "",
        ]
    lines += [
        "## Cost / feasibility",
        "",
        "| Method | Setup | Conventions | Deterministic | Offline | Value-aware | Statistical |",
        "| --- | --- | --- | :---: | :---: | :---: | :---: |",
    ]

    def _yn(value: bool) -> str:
        return "yes" if value else "no"

    for m in methods:
        f = m["feasibility"]
        lines.append(
            f"| {m['name']} | {f['setup_required']} | {f['conventions_assumed']} | "
            f"{_yn(f['deterministic'])} | {_yn(f['offline'])} | {_yn(f['value_aware'])} | "
            f"{_yn(f['statistical'])} |"
        )
    return "\n".join(lines) + "\n"
