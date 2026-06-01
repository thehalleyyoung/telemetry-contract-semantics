"""GitHub Action / CI surface: a deterministic one-shot observability report.

This module wraps the existing scan + diagnose engines into a single
deterministic "CI report" suitable for a GitHub Action: a diagnosability score,
severity counts, the top under-instrumentation gaps, and the unanswered incident
questions. It can compare against a base-branch report to produce a score delta,
render a concise PR comment, and evaluate a configurable pass/fail gate (score
floor + finding-severity threshold).

Everything is pure-stdlib and byte-deterministic: counts come from sorted
Counters, there is no wall-clock or RNG, and the same inputs always render the
same bytes.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .pipeline import collect_events, diagnose
from .repo_scan import scan_directory

CI_REPORT_SCHEMA = "telemetry-contracts/ci-report@1"
_SEVERITY_RANK = {"error": 3, "warning": 2, "info": 1}


def analyze_for_ci(
    root: str | Path, *, service: str | None = None, max_files: int = 300
) -> dict[str, Any]:
    """Produce a deterministic CI report for a repository checkout."""

    scan = scan_directory(root, service=service, max_files=max_files)
    events = collect_events(root)["events"]
    has_telemetry = bool(events)
    diag = diagnose(events, service=service) if has_telemetry else None

    findings = scan.get("findings", [])
    by_code: Counter[str] = Counter(f["code"] for f in findings)
    code_severity: dict[str, str] = {}
    for f in findings:
        code = f["code"]
        sev = f["severity"]
        if code not in code_severity or _SEVERITY_RANK.get(sev, 0) > _SEVERITY_RANK.get(code_severity[code], 0):
            code_severity[code] = sev
    top_gaps = [
        {"code": code, "count": count, "severity": code_severity.get(code, "warning")}
        for code, count in sorted(by_code.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    by_severity = {
        "error": sum(1 for f in findings if f["severity"] == "error"),
        "warning": sum(1 for f in findings if f["severity"] == "warning"),
        "info": sum(1 for f in findings if f["severity"] == "info"),
    }

    unanswered = (
        sorted(
            (
                {"id": q["id"], "question": q["question"], "gap": q["gap"]}
                for q in diag["unanswered_questions"]
            ),
            key=lambda q: q["id"],
        )
        if diag
        else []
    )

    return {
        "schema": CI_REPORT_SCHEMA,
        "has_telemetry": has_telemetry,
        "diagnosability_score": diag["diagnosability_score"] if diag else None,
        "verdict": diag["verdict"] if diag else "no telemetry discovered",
        "events": len(events),
        "service": service,
        "findings_total": len(findings),
        "by_severity": by_severity,
        "top_gaps": top_gaps,
        "unanswered_questions": unanswered,
    }


def compare_ci_reports(head: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    """Compare a head report against a base report (e.g. the PR base branch)."""

    head_score = head.get("diagnosability_score")
    base_score = base.get("diagnosability_score")
    score_delta = (
        head_score - base_score
        if isinstance(head_score, int) and isinstance(base_score, int)
        else None
    )
    head_gaps = {g["code"] for g in head.get("top_gaps", [])}
    base_gaps = {g["code"] for g in base.get("top_gaps", [])}
    return {
        "score_delta": score_delta,
        "base_score": base_score,
        "head_score": head_score,
        "new_gap_codes": sorted(head_gaps - base_gaps),
        "resolved_gap_codes": sorted(base_gaps - head_gaps),
    }


def evaluate_ci_gate_for_report(
    report: dict[str, Any], *, min_score: int | None = None, fail_on: str = "error"
) -> dict[str, Any]:
    """Evaluate a configurable pass/fail gate over a CI report.

    Fails when the diagnosability score is below ``min_score`` or when findings
    of severity ``fail_on`` (or worse) are present. ``fail_on='never'`` disables
    the severity gate.
    """

    reasons: list[str] = []
    score = report.get("diagnosability_score")
    if min_score is not None and isinstance(score, int) and score < min_score:
        reasons.append(f"diagnosability score {score} is below the floor {min_score}")

    if fail_on != "never":
        threshold = _SEVERITY_RANK.get(fail_on, 3)
        offending = {
            sev: report["by_severity"].get(sev, 0)
            for sev, rank in _SEVERITY_RANK.items()
            if rank >= threshold and report["by_severity"].get(sev, 0) > 0
        }
        if offending:
            detail = ", ".join(f"{n} {sev}" for sev, n in sorted(offending.items()))
            reasons.append(f"findings at or above '{fail_on}' severity: {detail}")

    return {"pass": not reasons, "reasons": reasons, "min_score": min_score, "fail_on": fail_on}


def _score_line(report: dict[str, Any], comparison: dict[str, Any] | None) -> str:
    if not report["has_telemetry"]:
        return "No telemetry was discovered, so no diagnosability score could be computed."
    score = report["diagnosability_score"]
    line = f"**Diagnosability score: {score}/100** — {report['verdict']}."
    if comparison and comparison.get("score_delta") is not None:
        delta = comparison["score_delta"]
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "▬")
        sign = f"+{delta}" if delta > 0 else str(delta)
        line += f" ({arrow} {sign} vs base {comparison['base_score']})"
    return line


def build_pr_comment(
    report: dict[str, Any], base: dict[str, Any] | None = None
) -> str:
    """Render a concise, deterministic PR comment from a CI report."""

    comparison = compare_ci_reports(report, base) if base else None
    lines = [
        "## 🔭 Observability report",
        "",
        _score_line(report, comparison),
        "",
        f"Scanned **{report['events']}** event(s); **{report['findings_total']}** "
        f"finding(s) (error: {report['by_severity']['error']}, "
        f"warning: {report['by_severity']['warning']}, "
        f"info: {report['by_severity']['info']}).",
        "",
    ]

    if report["top_gaps"]:
        lines += ["### Top gaps", "", "| Finding | Count | Severity |", "| --- | --: | --- |"]
        for gap in report["top_gaps"][:10]:
            lines.append(f"| `{gap['code']}` | {gap['count']} | {gap['severity']} |")
        lines.append("")

    if report["unanswered_questions"]:
        lines += ["### Incident questions left unanswered", ""]
        for q in report["unanswered_questions"]:
            lines.append(f"- **{q['question']}** (`{q['gap']}`)")
        lines.append("")

    if comparison:
        if comparison["new_gap_codes"]:
            lines.append(
                "⚠️ New gap classes vs base: "
                + ", ".join(f"`{c}`" for c in comparison["new_gap_codes"])
            )
        if comparison["resolved_gap_codes"]:
            lines.append(
                "✅ Resolved gap classes vs base: "
                + ", ".join(f"`{c}`" for c in comparison["resolved_gap_codes"])
            )
        if comparison["new_gap_codes"] or comparison["resolved_gap_codes"]:
            lines.append("")

    lines.append(
        "> Observability is a correctness property: these are *missing-evidence* "
        "findings on the telemetry this project already ships, not style notes."
    )
    return "\n".join(lines) + "\n"


def render_ci_report_markdown(report: dict[str, Any]) -> str:
    """Standalone (non-PR) markdown rendering of a CI report."""

    return build_pr_comment(report, None)
