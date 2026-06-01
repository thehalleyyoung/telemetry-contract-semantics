"""Staged, high-impact analysis pipeline for *pre-existing* repositories.

The pipeline turns "point me at a real repo" into a measurable improvement loop:

1. **Characterize** — inventory the telemetry/logs/source a repo already ships,
   detect its instrumentation libraries, and classify its archetype.
2. **Diagnose** — score how diagnosable the existing data is, list the incident
   questions it cannot answer, and rank fixes by leverage.
3. **Baseline** — infer execution semantics + an observed order as a formal
   anchor for later differential comparison.
4. **Plan** — emit a ranked, additive instrumentation plan with per-change
   predicted impact, provenance, and an LLM-fillable prompt pack (the model is
   optional; the plan and prompts are useful on their own).
5. **Apply (offline stand-in)** — deterministically synthesize the telemetry the
   planned instrumentation would emit, so the loop can verify impact without a
   live model or a running service.
6. **Differential** — re-diagnose and diff before/after: score delta, resolved
   vs introduced findings, newly answerable questions, and regressions.
7. **Iterate** — repeat until the predicted marginal impact falls below a
   threshold or the round/change caps are hit, accumulating an impact ledger.

Everything here is pure standard library and deterministic: no wall-clock
timestamps, no network, stable ordering. Acquisition (cloning a real GitHub
repo) is handled by :mod:`telemetry_contracts.repo_scan`; this module operates
on the working tree that produces.
"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .adapters import load_events_auto
from .discover import (
    _CORRELATION_FIELDS,
    _ERROR_EVIDENCE_FIELDS,
    _has_correlation,
    _has_error_evidence,
    _is_failure,
    _scalar_fields,
    analyze_events,
)
from .project_semantics import (
    find_source_files,
    group_events_by_service,
    infer_execution_semantics,
)
from .repo_scan import ContractLoadError, find_telemetry_files
from .code_proposals import generate_code_proposals

PLANNER = "telemetry-contracts/instrumentation-planner@1"

# Source-import signatures used to detect the instrumentation a repo already
# relies on (so later stages target the right APIs).
_INSTRUMENTATION_SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("opentelemetry", re.compile(r"\bopentelemetry\b|\botel\b", re.IGNORECASE)),
    ("prometheus", re.compile(r"\bprometheus_client\b|\bprom-client\b|\bprometheus\b", re.IGNORECASE)),
    ("statsd", re.compile(r"\bstatsd\b|\bdatadog\b|\bdogstatsd\b", re.IGNORECASE)),
    ("structlog", re.compile(r"\bstructlog\b", re.IGNORECASE)),
    ("python-logging", re.compile(r"^\s*import logging\b|logging\.getLogger", re.MULTILINE)),
    ("winston", re.compile(r"\bwinston\b", re.IGNORECASE)),
    ("pino", re.compile(r"\bpino\b", re.IGNORECASE)),
    ("zap", re.compile(r"\bgo\.uber\.org/zap\b", re.IGNORECASE)),
    ("slf4j", re.compile(r"\borg\.slf4j\b", re.IGNORECASE)),
    ("sentry", re.compile(r"\bsentry\b", re.IGNORECASE)),
)

_ARCHETYPE_SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("http-api", re.compile(r"\b(fastapi|flask|django|express|gin|spring|http\.server|@app\.route|app\.get\()\b", re.IGNORECASE)),
    ("consumer", re.compile(r"\b(kafka|rabbitmq|sqs|pubsub|celery|consumer|amqp)\b", re.IGNORECASE)),
    ("batch", re.compile(r"\b(cron|scheduler|batch|airflow|etl|pipeline)\b", re.IGNORECASE)),
    ("cli", re.compile(r"\b(argparse|click|cobra|__main__|sys\.argv)\b", re.IGNORECASE)),
)

# A secret is anything matching these high-precision patterns; characterization
# never echoes the value, only that a likely secret was seen.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
)

_MAX_SOURCE_SCAN_BYTES = 200_000
_MAX_SOURCE_FILES_FOR_DETECTION = 4000


# ---------------------------------------------------------------------------
# Stage 1: acquire + characterize a real repository's working tree
# ---------------------------------------------------------------------------


def collect_events(
    root: str | Path,
    *,
    max_files: int = 300,
    max_events: int = 200_000,
) -> dict[str, Any]:
    """Load and merge every telemetry record discoverable under ``root``."""

    root_path = Path(root)
    candidates = find_telemetry_files(root_path, max_files=max_files)
    events: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    formats: Counter[str] = Counter()
    for path in candidates:
        rel = str(path.relative_to(root_path))
        try:
            loaded = load_events_auto(path, tolerant=True)
        except (ContractLoadError, ValueError, OSError) as exc:
            skipped.append({"path": rel, "reason": str(exc)})
            continue
        loaded_events = loaded.get("events", [])
        if not loaded_events:
            skipped.append({"path": rel, "reason": "no telemetry records parsed"})
            continue
        room = max_events - len(events)
        if room <= 0:
            break
        chunk = loaded_events[:room]
        events.extend(chunk)
        formats[str(loaded.get("format"))] += 1
        files.append({"path": rel, "format": loaded.get("format"), "events": len(chunk)})
    return {
        "events": events,
        "files": files,
        "skipped": skipped,
        "formats": dict(sorted(formats.items())),
    }


def _git_commit(root: Path) -> str | None:
    head = root / ".git" / "HEAD"
    try:
        ref = head.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if ref.startswith("ref:"):
        target = root / ".git" / ref.split(" ", 1)[1].strip()
        try:
            return target.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return ref or None


def _detect_from_sources(source_files: list[str]) -> dict[str, Any]:
    libraries: set[str] = set()
    archetype_hits: Counter[str] = Counter()
    secrets_seen = 0
    for path in source_files[:_MAX_SOURCE_FILES_FOR_DETECTION]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                text = handle.read(_MAX_SOURCE_SCAN_BYTES)
        except OSError:
            continue
        for name, pattern in _INSTRUMENTATION_SIGNATURES:
            if pattern.search(text):
                libraries.add(name)
        for name, pattern in _ARCHETYPE_SIGNATURES:
            if pattern.search(text):
                archetype_hits[name] += 1
        for pattern in _SECRET_PATTERNS:
            secrets_seen += len(pattern.findall(text))
    archetype = "unknown"
    if archetype_hits:
        archetype = max(sorted(archetype_hits), key=lambda name: archetype_hits[name])
    return {
        "instrumentation_libraries": sorted(libraries),
        "archetype": archetype,
        "archetype_signals": dict(sorted(archetype_hits.items())),
        "likely_secrets_in_source": secrets_seen,
    }


def telemetry_inventory(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the telemetry a repo already emits, before any judgment."""

    by_kind: Counter[str] = Counter()
    services: set[str] = set()
    correlation_keys: set[str] = set()
    for event in events:
        by_kind[str(event.get("kind", "event"))] += 1
        service = event.get("service")
        if isinstance(service, str) and service:
            services.add(service)
        fields = _scalar_fields(event)
        for key in _CORRELATION_FIELDS:
            if event.get(key) not in (None, "") or fields.get(key) not in (None, ""):
                correlation_keys.add(key)
    return {
        "event_count": len(events),
        "by_kind": dict(sorted(by_kind.items())),
        "services": sorted(services),
        "correlation_keys": sorted(correlation_keys),
    }


def characterize_repo(
    root: str | Path,
    *,
    max_files: int = 300,
    max_events: int = 200_000,
) -> dict[str, Any]:
    """Stage 1: inventory + instrumentation + archetype + acquisition manifest."""

    root_path = Path(root)
    collected = collect_events(root_path, max_files=max_files, max_events=max_events)
    events = collected["events"]
    source_files = find_source_files(str(root_path))
    detection = _detect_from_sources(source_files)
    inventory = telemetry_inventory(events)
    has_telemetry = bool(events)

    next_steps: list[str] = []
    if not has_telemetry:
        next_steps = [
            "No telemetry/log data files were discovered in this repository.",
            "If logs live elsewhere, point the tools at that folder: characterize --path ./logs",
            "Or analyze a single log file directly: analyze --events your-logs.jsonl",
        ]

    return {
        "schema": "telemetry-contracts/repo-characterization@1",
        "manifest": {
            "root": str(root_path),
            "commit": _git_commit(root_path),
            "telemetry_files": len(collected["files"]),
            "source_files": len(source_files),
            "formats": collected["formats"],
            "file_budget": max_files,
        },
        "telemetry_inventory": inventory,
        "instrumentation_libraries": detection["instrumentation_libraries"],
        "archetype": detection["archetype"],
        "archetype_signals": detection["archetype_signals"],
        "likely_secrets_in_source": detection["likely_secrets_in_source"],
        "has_telemetry": has_telemetry,
        "files": collected["files"],
        "skipped": collected["skipped"],
        "next_steps": next_steps,
    }


# ---------------------------------------------------------------------------
# Stage 2: diagnose how usable the existing data is
# ---------------------------------------------------------------------------

# Each incident question is answerable only if the data carries the listed
# evidence on its failure (or, for latency, on its spans). The gap code links a
# question to the additive instrumentation that would unblock it.
_QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "which-request",
        "question": "Which request or trace does this failure belong to?",
        "gap": "missing-correlation",
        "evidence": "a trace_id / request_id / correlation_id on failure events",
    },
    {
        "id": "what-error",
        "question": "What error actually occurred?",
        "gap": "missing-error-evidence",
        "evidence": "an error_code, exception type/stack, or status on failure events",
    },
    {
        "id": "how-long",
        "question": "How long did the operation take?",
        "gap": "missing-duration",
        "evidence": "a duration_ms / latency field on span events",
    },
    {
        "id": "privacy-safe",
        "question": "Is the telemetry free of raw sensitive data?",
        "gap": "sensitive-values",
        "evidence": "redaction/hashing of values flagged as sensitive",
    },
)


def _has_duration(event: dict[str, Any], fields: dict[str, Any]) -> bool:
    for key in ("duration_ms", "duration", "latency_ms", "latency", "elapsed_ms", "elapsed"):
        value = event.get(key) if event.get(key) not in (None, "") else fields.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
    return False


def diagnose(events: list[dict[str, Any]], *, service: str | None = None) -> dict[str, Any]:
    """Stage 2: data-only diagnosability score, unanswered questions, leverage."""

    relevant = [e for e in events if service is None or e.get("service") in {service, None}]
    discovery = analyze_events(relevant, service=service)
    findings = discovery["findings"]
    by_code = discovery["summary"]["by_code"]

    failures = 0
    failures_without_correlation = 0
    failures_without_error = 0
    spans = 0
    spans_without_duration = 0
    for event in relevant:
        fields = _scalar_fields(event)
        if str(event.get("kind", "event")) in {"span", "spans"}:
            spans += 1
            if not _has_duration(event, fields):
                spans_without_duration += 1
        if _is_failure(event, fields):
            failures += 1
            if not _has_correlation(event, fields):
                failures_without_correlation += 1
            if not _has_error_evidence(fields):
                failures_without_error += 1
    sensitive = by_code.get("telemetry.sensitive_value", 0)

    # Per-question answerability and the events each gap blocks.
    blocked = {
        "missing-correlation": failures_without_correlation,
        "missing-error-evidence": failures_without_error,
        "missing-duration": spans_without_duration,
        "sensitive-values": sensitive,
    }
    unanswered: list[dict[str, Any]] = []
    answerable: list[dict[str, Any]] = []
    for question in _QUESTIONS:
        count = blocked.get(question["gap"], 0)
        record = {
            "id": question["id"],
            "question": question["question"],
            "gap": question["gap"],
            "missing_evidence": question["evidence"],
            "blocked_events": count,
        }
        (unanswered if count > 0 else answerable).append(record)

    # Deterministic 0-100 score: each component contributes a bounded penalty
    # proportional to the share of relevant events it blocks.
    total = max(len(relevant), 1)
    correlation_pen = 30 * (failures_without_correlation / total)
    error_pen = 25 * (failures_without_error / total)
    duration_pen = 15 * (spans_without_duration / total)
    privacy_pen = 30 * min(sensitive, total) / total
    score = int(round(max(0.0, 100.0 - correlation_pen - error_pen - duration_pen - privacy_pen)))

    # Leverage ranking: fixes ordered by how many blocked events (≈ unblocked
    # questions × reach) a single additive change would clear.
    leverage = sorted(
        ({"gap": q["gap"], "change": q["evidence"], "unblocks_question": q["id"], "events_affected": blocked.get(q["gap"], 0)}
         for q in _QUESTIONS if blocked.get(q["gap"], 0) > 0),
        key=lambda item: (-item["events_affected"], item["gap"]),
    )

    if sensitive > 0:
        verdict = "privacy-risky"
    elif failures_without_correlation or failures_without_error:
        verdict = "under-instrumented for incidents"
    elif score >= 80:
        verdict = "well-covered"
    else:
        verdict = "partially covered"

    return {
        "schema": "telemetry-contracts/diagnosis@1",
        "service": service,
        "event_count": len(relevant),
        "diagnosability_score": score,
        "components": {
            "failures": failures,
            "failures_without_correlation": failures_without_correlation,
            "failures_without_error_evidence": failures_without_error,
            "spans": spans,
            "spans_without_duration": spans_without_duration,
            "sensitive_values": sensitive,
        },
        "answerable_questions": answerable,
        "unanswered_questions": unanswered,
        "leverage_ranking": leverage,
        "verdict": verdict,
        "findings": findings,
        "findings_by_code": by_code,
    }


# ---------------------------------------------------------------------------
# Stage 3: formal baseline
# ---------------------------------------------------------------------------


def _proof_obligations(diagnosis: dict[str, Any]) -> list[dict[str, Any]]:
    """Express each incident question as a proof obligation the data discharges or not.

    This connects the data-only first pass to the formal layer: an obligation is
    ``discharged`` only when no relevant event is missing the required evidence.
    """

    obligations: list[dict[str, Any]] = []
    for record in diagnosis["answerable_questions"]:
        obligations.append({
            "obligation": record["id"],
            "claim": record["question"],
            "required_evidence": record["missing_evidence"],
            "status": "discharged",
            "blocking_events": 0,
        })
    for record in diagnosis["unanswered_questions"]:
        obligations.append({
            "obligation": record["id"],
            "claim": record["question"],
            "required_evidence": record["missing_evidence"],
            "status": "not_discharged",
            "blocking_events": record["blocked_events"],
        })
    return sorted(obligations, key=lambda o: (o["status"] != "not_discharged", o["obligation"]))


def _ordering_evidence(order: dict[str, Any] | None) -> dict[str, Any]:
    """Surface auditable per-chain ordering support, or what would unlock it.

    The inferred order is a *candidate* discovered from correlated groups, not a
    proven execution order; the support metadata makes its strength auditable.
    """

    if not order:
        return {
            "order_inferred": False,
            "reason": "no confident order could be inferred from the observed data",
            "evidence_needed": [
                "a shared correlation key (trace_id/request_id) linking related signals",
                "at least two correlation groups containing the same pair of signals",
                "a consistent strict precedence of one signal before another across those groups",
            ],
        }
    return {
        "order_inferred": True,
        "candidate_only": True,
        "correlation_key": order.get("correlation_key"),
        "steps": [f"{s['kind']}:{s['name']}" for s in order.get("steps", [])],
        "enforceable": order.get("enforceable"),
        "support": {
            "supporting_groups": order.get("support_full_groups"),
            "partial_groups": order.get("partial_groups"),
            "window_ms": order.get("window_ms"),
        },
    }


def baseline(events: list[dict[str, Any]], *, service: str | None = None) -> dict[str, Any]:
    """Stage 3: inferred execution semantics + diagnosis as a snapshot anchor."""

    semantics = infer_execution_semantics(events, service=service, infer_sequences=True)
    diagnosis = diagnose(events, service=service)
    structure = semantics["event_structure"]
    order = semantics.get("inferred_ordering")
    concurrency_pairs = structure["concurrency_pair_count"]
    obligations = _proof_obligations(diagnosis)
    return {
        "schema": "telemetry-contracts/baseline@1",
        "service": semantics.get("service"),
        "diagnosability_score": diagnosis["diagnosability_score"],
        "verdict": diagnosis["verdict"],
        "semantics": semantics["semantics"],
        "inferred_ordering": order,
        "order_inferred": order is not None,
        "ordering_evidence": _ordering_evidence(order),
        "concurrency_pairs": concurrency_pairs,
        "concurrency_risk": {
            "candidate_concurrent_pairs": concurrency_pairs,
            "note": (
                "signal pairs observed with no consistent order across correlation "
                "groups — candidate concurrency the source may assume is sequential; "
                "review as a possible correctness risk, not a proven race"
            ) if concurrency_pairs else "no candidate concurrency risks observed",
        },
        "proof_obligations": obligations,
        "obligations_discharged": sum(1 for o in obligations if o["status"] == "discharged"),
        "obligations_outstanding": sum(1 for o in obligations if o["status"] == "not_discharged"),
        "unanswered_questions": [q["id"] for q in diagnosis["unanswered_questions"]],
    }


# ---------------------------------------------------------------------------
# Stage 4: high-impact, additive instrumentation plan (LLM-fillable)
# ---------------------------------------------------------------------------

_ACTION_BY_GAP = {
    "missing-correlation": "propagate and attach a trace_id/request_id onto this signal",
    "missing-error-evidence": "attach an error_code and exception type/status on failure paths",
    "missing-duration": "record a duration_ms when the span completes",
    "sensitive-values": "redact or hash the sensitive field before it is emitted",
}


def instrumentation_plan(
    diagnosis: dict[str, Any],
    *,
    libraries: list[str] | None = None,
    max_changes: int = 5,
    exclude_gaps: set[str] | None = None,
) -> dict[str, Any]:
    """Stage 4: rank additive instrumentation changes by predicted impact.

    Each change carries provenance and an LLM-fillable prompt pack. Privacy
    gaps are emitted as *review-required* changes rather than auto-applied code.
    ``exclude_gaps`` drops gaps already deferred or quarantined in earlier
    rounds, which guarantees the loop terminates rather than retrying them.
    """

    libraries = libraries or []
    exclude_gaps = exclude_gaps or set()
    primary_lib = libraries[0] if libraries else "your logging/telemetry library"
    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for rank, item in enumerate(diagnosis.get("leverage_ranking", [])):
        gap = item["gap"]
        if gap in exclude_gaps:
            continue
        change = {
            "id": f"chg-{rank + 1:02d}-{gap}",
            "gap": gap,
            "action": _ACTION_BY_GAP.get(gap, item["change"]),
            "target": item["change"],
            "predicted_impact": {
                "events_affected": item["events_affected"],
                "questions_unblocked": [item["unblocks_question"]],
                "score_points_expected": _expected_points(gap, item["events_affected"], diagnosis["event_count"]),
            },
            "rationale": f"{item['events_affected']} event(s) are blocked on: {item['change']}.",
            "provenance": {"generator": PLANNER, "gap": gap, "source": "diagnosis@1"},
            "prompt_pack": _prompt_pack(gap, item, primary_lib),
            "additive_only": True,
            "requires_human_review": gap == "sensitive-values",
        }
        if gap == "sensitive-values":
            # Never auto-generate code that touches sensitive data paths.
            change["note"] = "privacy-sensitive: emitted as a review-required change, not auto-applied code"
            skipped.append(change)
        else:
            planned.append(change)
        if len(planned) >= max_changes:
            break

    return {
        "schema": "telemetry-contracts/instrumentation-plan@1",
        "service": diagnosis.get("service"),
        "instrumentation_libraries": libraries,
        "planned_changes": planned,
        "review_required_changes": skipped,
        "generator": PLANNER,
    }


def _expected_points(gap: str, events_affected: int, total: int) -> int:
    weights = {"missing-correlation": 30, "missing-error-evidence": 25, "missing-duration": 15, "sensitive-values": 30}
    if total <= 0:
        return 0
    return int(round(weights.get(gap, 10) * (events_affected / total)))


def _prompt_pack(gap: str, item: dict[str, Any], library: str) -> dict[str, Any]:
    return {
        "system": (
            "You add ONLY additive observability instrumentation. Never change business "
            "logic, control flow, or return values. Emit a minimal unified diff."
        ),
        "instruction": (
            f"Using {library}, {_ACTION_BY_GAP.get(gap, item['change'])}. "
            "Do not log raw secrets or PII. Keep the change small and reviewable."
        ),
        "acceptance": (
            f"After the change, emitted telemetry must satisfy: {item['change']}. "
            f"This should unblock the incident question '{item['unblocks_question']}'."
        ),
        "context_needed": ["the file and function that emits this signal", "the existing telemetry call to extend"],
    }


# ---------------------------------------------------------------------------
# Stage 5: apply (offline, deterministic stand-in for generated code)
# ---------------------------------------------------------------------------


def synthesize_instrumentation(
    events: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Stage 5 (offline): emit the telemetry the planned changes *would* produce.

    This deterministically simulates applying the approved, additive
    instrumentation so the loop can measure impact without a live model or a
    running service. Every modified record is tagged ``_synthetic: True``.
    """

    gaps = {change["gap"] for change in plan.get("planned_changes", [])}
    applied: Counter[str] = Counter()
    out: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        new_event = dict(event)
        fields = _scalar_fields(event)
        touched = False
        if "missing-correlation" in gaps and _is_failure(event, fields) and not _has_correlation(event, fields):
            new_event["trace_id"] = f"synthetic-trace-{index}"
            applied["missing-correlation"] += 1
            touched = True
        if "missing-error-evidence" in gaps and _is_failure(event, fields) and not _has_error_evidence(fields):
            new_event.setdefault("error_code", "SYNTHETIC_ERROR")
            new_event.setdefault("exception_type", "SyntheticError")
            applied["missing-error-evidence"] += 1
            touched = True
        if "missing-duration" in gaps and str(event.get("kind", "event")) in {"span", "spans"} and not _has_duration(event, fields):
            new_event.setdefault("duration_ms", 1)
            applied["missing-duration"] += 1
            touched = True
        if touched:
            new_event["_synthetic"] = True
        out.append(new_event)
    return {
        "events": out,
        "applied_by_gap": dict(sorted(applied.items())),
        "synthetic": True,
    }


def verify_instrumentation(events_after: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    """Stage 5: confirm each planned change actually shows up in the new data."""

    after = diagnose(events_after, service=plan.get("service"))
    blocked_after = {item["gap"]: item["events_affected"] for item in after["leverage_ranking"]}
    results = []
    for change in plan.get("planned_changes", []):
        remaining = blocked_after.get(change["gap"], 0)
        results.append({
            "id": change["id"],
            "gap": change["gap"],
            "fulfilled": remaining == 0,
            "remaining_blocked_events": remaining,
        })
    return {"changes": results, "all_fulfilled": all(r["fulfilled"] for r in results) if results else True}


# ---------------------------------------------------------------------------
# Stage 6: differential before vs after
# ---------------------------------------------------------------------------


def differential(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Stage 6: diff two diagnoses; detect improvement and regressions."""

    before_codes = Counter(before.get("findings_by_code", {}))
    after_codes = Counter(after.get("findings_by_code", {}))
    resolved = {code: before_codes[code] - after_codes.get(code, 0)
                for code in before_codes if before_codes[code] > after_codes.get(code, 0)}
    introduced = {code: after_codes[code] - before_codes.get(code, 0)
                  for code in after_codes if after_codes[code] > before_codes.get(code, 0)}

    before_q = {q["id"] for q in before.get("unanswered_questions", [])}
    after_q = {q["id"] for q in after.get("unanswered_questions", [])}
    newly_answerable = sorted(before_q - after_q)
    newly_blocked = sorted(after_q - before_q)

    score_delta = after["diagnosability_score"] - before["diagnosability_score"]
    regressions: list[str] = []
    if score_delta < 0:
        regressions.append(f"diagnosability score dropped by {-score_delta}")
    if introduced:
        regressions.append(f"introduced findings: {', '.join(sorted(introduced))}")
    if newly_blocked:
        regressions.append(f"newly unanswerable: {', '.join(newly_blocked)}")

    summary = (
        f"score {before['diagnosability_score']} -> {after['diagnosability_score']} "
        f"({'+' if score_delta >= 0 else ''}{score_delta}); "
        f"{len(newly_answerable)} question(s) newly answerable; "
        f"{sum(resolved.values())} finding(s) resolved; "
        f"{len(regressions)} regression(s)."
    )
    return {
        "schema": "telemetry-contracts/differential@1",
        "score_delta": score_delta,
        "resolved_findings": dict(sorted(resolved.items())),
        "introduced_findings": dict(sorted(introduced.items())),
        "newly_answerable": newly_answerable,
        "newly_unanswerable": newly_blocked,
        "regressions": regressions,
        "improved": score_delta > 0 and not regressions,
        "summary": summary,
    }


def semantic_differential(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Diff two ``baseline`` snapshots: new signals, fields, ordering, coverage.

    Surfaces temporal sequences that became enforceable only after the added
    instrumentation, plus changes in ordering support and discharged obligations.
    """

    def _signals(b: dict[str, Any]) -> set[str]:
        order = b.get("inferred_ordering") or {}
        return {f"{s['kind']}:{s['name']}" for s in order.get("steps", [])}

    before_signals = _signals(before)
    after_signals = _signals(after)
    before_order = before.get("inferred_ordering") or {}
    after_order = after.get("inferred_ordering") or {}

    before_enforceable = bool(before_order.get("enforceable"))
    after_enforceable = bool(after_order.get("enforceable"))
    newly_enforceable_sequence = (not before_enforceable) and after_enforceable

    before_support = (before_order or {}).get("support_full_groups") or 0
    after_support = (after_order or {}).get("support_full_groups") or 0

    obligations_before = before.get("obligations_discharged", 0)
    obligations_after = after.get("obligations_discharged", 0)

    return {
        "schema": "telemetry-contracts/semantic-differential@1",
        "new_signals": sorted(after_signals - before_signals),
        "lost_signals": sorted(before_signals - after_signals),
        "order_inferred_before": before.get("order_inferred", False),
        "order_inferred_after": after.get("order_inferred", False),
        "order_newly_inferred": (not before.get("order_inferred", False)) and after.get("order_inferred", False),
        "newly_enforceable_sequence": newly_enforceable_sequence,
        "ordering_support_delta": after_support - before_support,
        "obligations_discharged_delta": obligations_after - obligations_before,
        "concurrency_pairs_before": before.get("concurrency_pairs", 0),
        "concurrency_pairs_after": after.get("concurrency_pairs", 0),
    }


def _application_manifest(
    round_index: int,
    commit: str | None,
    plan: dict[str, Any],
    applied_by_gap: dict[str, int],
    events_before: int,
    events_after: int,
    quarantined: bool,
    safety: dict[str, Any],
) -> dict[str, Any]:
    """Record exactly what was (synthetically) applied, deferred, or quarantined.

    The application is an offline, deterministic stand-in for generated code:
    it is never written to the user's repository and no target build/test is run.
    Privacy/review changes are deferred; a round that regresses safety is
    quarantined and rolled back (its effect is excluded from realized impact).
    """

    changes: list[dict[str, Any]] = []
    for change in plan.get("planned_changes", []):
        gap = change["gap"]
        changes.append({
            "id": change["id"],
            "gap": gap,
            "status": "quarantined" if quarantined else "accepted",
            "would_affect_events": change["predicted_impact"]["events_affected"],
            "synthetic_events_added": applied_by_gap.get(gap, 0),
        })
    for change in plan.get("review_required_changes", []):
        changes.append({
            "id": change["id"],
            "gap": change["gap"],
            "status": "deferred_privacy",
            "would_affect_events": change["predicted_impact"]["events_affected"],
            "synthetic_events_added": 0,
        })
    return {
        "schema": "telemetry-contracts/application-manifest@1",
        "round": round_index,
        "source_commit": commit,
        "state_id": f"{commit or 'unknown-sha'}+synthetic-r{round_index}",
        "synthetic": True,
        "applied_to_repo": False,
        "target_repo_build_not_run": True,
        "quarantined": quarantined,
        "safety_gate": safety,
        "events_before": events_before,
        "events_after_if_kept": events_after,
        "applied_by_gap": dict(sorted(applied_by_gap.items())),
        "changes": sorted(changes, key=lambda c: c["id"]),
    }


# ---------------------------------------------------------------------------
# Stage 7: orchestrate the staged loop to convergence
# ---------------------------------------------------------------------------


def run_pipeline(
    root: str | Path,
    *,
    rounds: int = 3,
    max_changes_per_round: int = 5,
    min_marginal_impact: int = 1,
    service: str | None = None,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the full acquire→diagnose→plan→apply→differential loop offline.

    Stops early when a round has no planned changes or the predicted marginal
    impact (expected score points) falls below ``min_marginal_impact``. Each
    round is gated for safety: a round whose differential introduces a new
    finding, drops the score, or makes a question newly unanswerable is
    quarantined and rolled back, so improvement never silently regresses safety.

    When ``out_dir`` is given, every stage is persisted as a content-addressable,
    SHA-keyed artifact carrying provenance.
    """

    root_path = Path(root)
    characterization = characterize_repo(root_path)
    collected = collect_events(root_path)
    libraries = characterization["instrumentation_libraries"]

    options = {
        "rounds": rounds,
        "max_changes_per_round": max_changes_per_round,
        "min_marginal_impact": min_marginal_impact,
        "service": service,
    }

    if not collected["events"]:
        empty = {
            "schema": "telemetry-contracts/pipeline@1",
            "characterization": characterization,
            "baseline": None,
            "rounds": [],
            "impact_ledger": [],
            "stopped_reason": "no telemetry discovered",
            "regressed": False,
            "final": None,
        }
        if out_dir is not None:
            empty["artifacts"] = _persist(empty, out_dir, options)
        return empty

    services = sorted(group_events_by_service(collected["events"])) if service is None else [service]
    # Run the loop on the dominant service for a single coherent narrative;
    # the per-service breakdown is available via scan --deep.
    target_service = None if services == ["(unspecified)"] else services[0]
    if target_service == "(unspecified)":
        target_service = None

    events = collected["events"]
    initial_baseline = baseline(events, service=target_service)
    current = diagnose(events, service=target_service)
    round_reports: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    excluded_gaps: set[str] = set()
    any_regression = False
    stopped_reason = "rounds exhausted"
    commit = characterization["manifest"].get("commit")

    for round_index in range(1, rounds + 1):
        plan = instrumentation_plan(
            current, libraries=libraries, max_changes=max_changes_per_round, exclude_gaps=excluded_gaps,
        )
        planned = plan["planned_changes"]
        if not planned:
            stopped_reason = "no further safety-approved high-impact changes"
            break
        predicted = sum(c["predicted_impact"]["score_points_expected"] for c in planned)
        if predicted < min_marginal_impact:
            stopped_reason = f"predicted marginal impact {predicted} < threshold {min_marginal_impact}"
            break

        # Synthesize onto a CANDIDATE copy; never advance state until the safety
        # gate passes, so a regressing round cannot contaminate later rounds.
        candidate = synthesize_instrumentation(events, plan)
        proposals = generate_code_proposals(plan, libraries=libraries, commit=commit)
        verification = verify_instrumentation(candidate["events"], plan)
        candidate_diag = diagnose(candidate["events"], service=target_service)
        diff = differential(current, candidate_diag)
        sem_diff = semantic_differential(
            initial_baseline if round_index == 1 else baseline(events, service=target_service),
            baseline(candidate["events"], service=target_service),
        )

        quarantined = bool(diff["regressions"])
        safety = {
            "passed": not quarantined,
            "reasons": diff["regressions"],
        }
        manifest = _application_manifest(
            round_index, commit, plan, candidate["applied_by_gap"],
            len(events), len(candidate["events"]), quarantined, safety,
        )

        round_reports.append({
            "round": round_index,
            "plan": plan,
            "code_proposals": proposals,
            "application_manifest": manifest,
            "applied_by_gap": candidate["applied_by_gap"],
            "verification": verification,
            "differential": diff,
            "semantic_differential": sem_diff,
            "quarantined": quarantined,
            "score_after": candidate_diag["diagnosability_score"],
        })
        ledger.append({
            "round": round_index,
            "predicted_score_points": predicted,
            "realized_score_delta": 0 if quarantined else diff["score_delta"],
            "changes_applied": 0 if quarantined else len(planned),
            "quarantined": quarantined,
            "regressions": len(diff["regressions"]),
        })

        if quarantined:
            # Roll back: discard the candidate, exclude these gaps so we do not
            # retry them, and keep looking for other safe, high-impact changes.
            any_regression = True
            excluded_gaps.update(c["gap"] for c in planned)
            continue

        events = candidate["events"]
        current = candidate_diag
        if diff["score_delta"] <= 0:
            stopped_reason = "no measurable improvement from last round"
            break

    final_diff = differential(
        {"diagnosability_score": initial_baseline["diagnosability_score"],
         "findings_by_code": diagnose(collected["events"], service=target_service)["findings_by_code"],
         "unanswered_questions": [{"id": q} for q in initial_baseline["unanswered_questions"]]},
        current,
    )
    final_sem_diff = semantic_differential(initial_baseline, baseline(events, service=target_service))
    report = {
        "schema": "telemetry-contracts/pipeline@1",
        "characterization": characterization,
        "service": target_service,
        "baseline": initial_baseline,
        "rounds": round_reports,
        "impact_ledger": ledger,
        "stopped_reason": stopped_reason,
        "regressed": any_regression,
        "final": {
            "diagnosability_score": current["diagnosability_score"],
            "verdict": current["verdict"],
            "remaining_unanswered": [q["id"] for q in current["unanswered_questions"]],
            "overall_differential": final_diff,
            "overall_semantic_differential": final_sem_diff,
        },
    }
    if out_dir is not None:
        report["artifacts"] = _persist(report, out_dir, options)
    return report


def _persist(report: dict[str, Any], out_dir: str | Path, options: dict[str, Any]) -> dict[str, Any]:
    """Write artifacts and return the (path-free) index for embedding in the report."""

    from .artifacts import write_pipeline_artifacts

    index = write_pipeline_artifacts(report, out_dir, options=options)
    # Embed only relative paths + content hashes (no absolute out_dir) so the
    # report stays byte-deterministic across machines.
    return index


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_characterization_text(report: dict[str, Any]) -> str:
    inv = report["telemetry_inventory"]
    manifest = report["manifest"]
    lines = [
        f"Repository: {manifest['root']}" + (f" @ {manifest['commit'][:12]}" if manifest.get("commit") else ""),
        f"Archetype: {report['archetype']}",
        f"Instrumentation: {', '.join(report['instrumentation_libraries']) or 'none detected'}",
        f"Telemetry: {inv['event_count']} event(s) across {manifest['telemetry_files']} file(s); "
        f"kinds={inv['by_kind'] or '{}'}; services={inv['services'] or '[]'}",
        f"Correlation keys present: {', '.join(inv['correlation_keys']) or 'none'}",
        f"Source files scanned: {manifest['source_files']}; likely secrets in source: {report['likely_secrets_in_source']}",
    ]
    if not report["has_telemetry"]:
        lines.append("")
        lines.extend(report["next_steps"])
    return "\n".join(lines)


def format_diagnosis_text(report: dict[str, Any]) -> str:
    lines = [
        f"Diagnosability score: {report['diagnosability_score']}/100  ({report['verdict']})",
        f"Events analyzed: {report['event_count']}",
    ]
    if report["unanswered_questions"]:
        lines.append("")
        lines.append("Unanswered incident questions (most blocking first):")
        for item in sorted(report["unanswered_questions"], key=lambda q: -q["blocked_events"]):
            lines.append(f"  - {item['question']}")
            lines.append(f"      needs: {item['missing_evidence']} ({item['blocked_events']} event(s) blocked)")
    else:
        lines.append("All tracked incident questions are answerable from the existing data.")
    if report["leverage_ranking"]:
        lines.append("")
        lines.append("Highest-leverage fixes:")
        for item in report["leverage_ranking"]:
            lines.append(f"  - {item['change']}  (+~{item['events_affected']} events unblocked)")
    return "\n".join(lines)


def format_pipeline_text(report: dict[str, Any]) -> str:
    if report["final"] is None:
        lines = ["Telemetry improvement pipeline", ""]
        lines.append(format_characterization_text(report["characterization"]))
        lines.append("")
        lines.append(f"Stopped: {report['stopped_reason']}")
        return "\n".join(lines)
    char = report["characterization"]
    base = report["baseline"]
    final = report["final"]
    lines = [
        "Telemetry improvement pipeline",
        "",
        f"Archetype: {char['archetype']}; instrumentation: "
        f"{', '.join(char['instrumentation_libraries']) or 'none detected'}",
        f"Baseline score: {base['diagnosability_score']}/100 ({base['verdict']})",
        f"Order inferred at baseline: {'yes' if base['order_inferred'] else 'no'}",
        "",
    ]
    for entry in report["rounds"]:
        diff = entry["differential"]
        lines.append(f"Round {entry['round']}: {diff['summary']}")
        for change in entry["plan"]["planned_changes"]:
            lines.append(
                f"    + {change['action']} "
                f"(predicted +{change['predicted_impact']['score_points_expected']} pts)"
            )
    lines.append("")
    lines.append(
        f"Final score: {final['diagnosability_score']}/100 ({final['verdict']}); "
        f"overall {final['overall_differential']['summary']}"
    )
    lines.append(f"Stopped: {report['stopped_reason']}")
    if final["remaining_unanswered"]:
        lines.append(f"Still unanswered: {', '.join(final['remaining_unanswered'])}")
    return "\n".join(lines)
