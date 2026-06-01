"""Contract-free discovery checks.

This is the headline "use it right now" entry point: point it at the telemetry
you already emit and get an actionable observability/privacy report immediately,
with **no contract to author first**. The checks here are heuristics that hold
without a contract — raw secret/PII emission, unclassified tenant identifiers,
missing correlation on failures, high-cardinality metric labels, and error
events that lack failure evidence.

Findings reuse the established taxonomy codes whose meaning is contract-free, so
SARIF export, CI gating, and the finding taxonomy all keep working unchanged.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .findings import Finding
from .validator import (
    SENSITIVE_FIELD_NAMES,
    TENANT_IDENTIFIER_FIELD_NAMES,
)
import re

# How many examples of the same finding code to keep, so a noisy log file does
# not bury the actionable signal.
_MAX_EXAMPLES_PER_CODE = 25
# Minimum sample size before we trust a high-cardinality verdict.
_MIN_CARDINALITY_SAMPLE = 20
_CARDINALITY_DISTINCT_FLOOR = 50
_CARDINALITY_RATIO = 0.8

# High-precision content patterns scanned on every value (very low false-positive
# rate on arbitrary logs). Noisier patterns (credit card, phone) are only applied
# when the field name itself suggests that data type, to keep first-run output
# trustworthy on data you already have.
_HIGH_PRECISION_VALUE_PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    "bearer_token": re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    "password_assignment": re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*[^,\s]+"),
}
_CARD_VALUE_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_PHONE_VALUE_PATTERN = re.compile(r"(?<![\w-])(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?![\w-])")
_CARD_FIELD_NAMES = re.compile(r"(?i)(credit[_-]?card|card[_-]?number|\bpan\b|cc[_-]?num)")
_PHONE_FIELD_NAMES = re.compile(r"(?i)(phone|mobile|\btel\b|telephone|msisdn)")
# Structural correlation fields are not "sensitive values" even when numeric.
_STRUCTURAL_FIELDS = re.compile(r"(?i)^(trace|span|parent_span|parent|request|correlation|session)_?id$|^(span_id|trace_id|timestamp(_ms)?|_line)$")

_ERROR_SEVERITIES = {"ERROR", "ERR", "FATAL", "CRITICAL", "CRIT", "SEVERE", "ALERT", "EMERGENCY"}
_ERROR_EVIDENCE_FIELDS = ("error_code", "error", "errorcode", "exception", "exception_type", "stack", "stack_trace", "stacktrace", "status", "status_code", "error_message")
_CORRELATION_FIELDS = ("trace_id", "span_id", "request_id", "correlation_id")
_SAFE_TRANSFORM = re.compile(r"(?i)^(<?redacted>?|\[redacted\]|\*+|<omitted>|sha256:[a-f0-9]{8,}|hash:|tok_|tokenized:)")


def analyze_events(events: list[dict[str, Any]], *, service: str | None = None) -> dict[str, Any]:
    """Run zero-config heuristic checks over already-collected telemetry."""

    relevant = [event for event in events if service is None or event.get("service") in {service, None}]
    counts: dict[str, int] = defaultdict(int)
    findings: list[Finding] = []

    def emit(finding: Finding) -> None:
        counts[finding.code] += 1
        if counts[finding.code] <= _MAX_EXAMPLES_PER_CODE:
            findings.append(finding)

    for event in relevant:
        index = _index(event)
        kind = str(event.get("kind", "event"))
        confidence = event.get("_kind_confidence", "high")
        fields = _scalar_fields(event)

        for field_name, value in fields.items():
            emit_sensitive = _sensitive_value_finding(field_name, value, index)
            if emit_sensitive is not None:
                emit(emit_sensitive)
                continue
            unclassified = _unclassified_identifier_finding(field_name, value, index)
            if unclassified is not None:
                emit(unclassified)

        if _is_failure(event, fields) and confidence != "low":
            if not _has_correlation(event, fields):
                emit(
                    Finding(
                        "warning",
                        "telemetry.correlation_missing",
                        f"{kind} '{event.get('name', '?')}' reports a failure but carries no correlation id (trace_id/request_id)",
                        f"event[{index}]",
                        None,
                        index,
                    )
                )
            if not _has_error_evidence(fields):
                emit(
                    Finding(
                        "warning",
                        "discovery.missing_error_evidence",
                        f"{kind} '{event.get('name', '?')}' reports a failure but carries no error code, exception, or status evidence",
                        f"event[{index}]",
                        None,
                        index,
                    )
                )

    findings.extend(_cardinality_findings(relevant, emit_guard=counts))

    summary = _summary(relevant, findings, counts)
    return {
        "schema": "telemetry-contracts/discovery@1",
        "service": service,
        "summary": summary,
        "findings": [finding.to_dict() for finding in findings],
    }


def _sensitive_value_finding(field_name: str, value: Any, index: int | None) -> Finding | None:
    if not isinstance(value, str) or not value:
        return None
    if _STRUCTURAL_FIELDS.search(field_name):
        return None
    if _SAFE_TRANSFORM.match(value.strip()):
        return None
    matched = next((label for label, pattern in _HIGH_PRECISION_VALUE_PATTERNS.items() if pattern.search(value)), None)
    if matched is None and _CARD_FIELD_NAMES.search(field_name) and _CARD_VALUE_PATTERN.search(value):
        matched = "credit_card"
    if matched is None and _PHONE_FIELD_NAMES.search(field_name) and _PHONE_VALUE_PATTERN.search(value):
        matched = "phone"
    if matched is None:
        return None
    return Finding(
        "error",
        "telemetry.sensitive_value",
        f"field '{field_name}' appears to contain raw sensitive data ({matched})",
        f"event[{index}].{field_name}",
        None,
        index,
        {"pattern": matched, "preview": _redact(value)},
    )


def _unclassified_identifier_finding(field_name: str, value: Any, index: int | None) -> Finding | None:
    if value is None or value == "":
        return None
    if isinstance(value, str) and _SAFE_TRANSFORM.match(value.strip()):
        return None
    if SENSITIVE_FIELD_NAMES.search(field_name) or TENANT_IDENTIFIER_FIELD_NAMES.search(field_name):
        return Finding(
            "warning",
            "telemetry.sensitive_unclassified",
            f"field '{field_name}' looks sensitive but is emitted without redaction/hashing or a privacy classification",
            f"event[{index}].{field_name}",
            None,
            index,
        )
    return None


def _cardinality_findings(events: list[dict[str, Any]], *, emit_guard: dict[str, int]) -> list[Finding]:
    by_metric: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("kind") != "metric":
            continue
        name = event.get("name")
        if isinstance(name, str):
            by_metric[(str(event.get("service")), name)].append(event)
    findings: list[Finding] = []
    for (_, name), metric_events in sorted(by_metric.items()):
        if len(metric_events) < _MIN_CARDINALITY_SAMPLE:
            continue
        label_values: dict[str, set[Any]] = defaultdict(set)
        for event in metric_events:
            for label, value in _scalar_fields(event).items():
                if isinstance(value, (str, int, float, bool)):
                    label_values[label].add(value)
        for label, values in sorted(label_values.items()):
            distinct = len(values)
            if distinct >= _CARDINALITY_DISTINCT_FLOOR and distinct >= _CARDINALITY_RATIO * len(metric_events):
                if emit_guard.get("telemetry.cardinality", 0) >= _MAX_EXAMPLES_PER_CODE:
                    continue
                emit_guard["telemetry.cardinality"] = emit_guard.get("telemetry.cardinality", 0) + 1
                findings.append(
                    Finding(
                        "warning",
                        "telemetry.cardinality",
                        f"metric '{name}' label '{label}' has {distinct} distinct values across {len(metric_events)} points (likely unbounded cardinality)",
                        f"metric[{name}].{label}",
                        None,
                        None,
                        {"distinct_values": distinct, "sample": len(metric_events)},
                    )
                )
    return findings


def _scalar_fields(event: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for container in ("attributes", "tags", "fields"):
        values = event.get(container)
        if isinstance(values, dict):
            for key, value in values.items():
                fields.setdefault(str(key), value)
    for key, value in event.items():
        if key in {"attributes", "tags", "fields", "kind", "name", "service", "_line"} or str(key).startswith("_"):
            continue
        fields.setdefault(str(key), value)
    return fields


def _is_failure(event: dict[str, Any], fields: dict[str, Any]) -> bool:
    severity = event.get("severity")
    if isinstance(severity, str) and severity.strip().upper() in _ERROR_SEVERITIES:
        return True
    for key in ("result", "status", "outcome", "state"):
        value = fields.get(key)
        if isinstance(value, str) and value.strip().lower() in {"error", "failed", "failure", "fail", "ko"}:
            return True
    status_code = fields.get("status_code") or fields.get("http.status_code")
    if isinstance(status_code, (int, float)) and not isinstance(status_code, bool) and status_code >= 500:
        return True
    return False


def _has_correlation(event: dict[str, Any], fields: dict[str, Any]) -> bool:
    for key in _CORRELATION_FIELDS:
        if event.get(key) not in (None, ""):
            return True
        if fields.get(key) not in (None, ""):
            return True
    return False


def _has_error_evidence(fields: dict[str, Any]) -> bool:
    lowered = {key.lower(): value for key, value in fields.items()}
    return any(lowered.get(field) not in (None, "") for field in _ERROR_EVIDENCE_FIELDS)


def _redact(value: str) -> str:
    text = value if len(value) <= 12 else f"{value[:6]}…{value[-2:]}"
    return f"<redacted:{len(value)} chars:{text[:3]}…>"


def _index(event: dict[str, Any]) -> int | None:
    line = event.get("_line")
    return line if isinstance(line, int) else None


def _summary(events: list[dict[str, Any]], findings: list[Finding], counts: dict[str, int]) -> dict[str, Any]:
    by_severity: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
    return {
        "events": len(events),
        "findings": sum(counts.values()),
        "shown_findings": len(findings),
        "by_severity": by_severity,
        "by_code": dict(sorted(counts.items())),
    }


def format_discovery_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Telemetry discovery report",
        "",
        f"Analyzed {summary['events']} events with **no contract required**.",
        "",
        f"- Findings: {summary['findings']} ({summary['by_severity']['error']} error, {summary['by_severity']['warning']} warning)",
    ]
    if report.get("service"):
        lines.insert(2, f"Service filter: `{report['service']}`")
    if not report["findings"]:
        lines.extend(["", "No diagnosability or privacy issues detected in the sampled telemetry.", ""])
        return "\n".join(lines)
    lines.extend(["", "| Severity | Code | Message | Location |", "| --- | --- | --- | --- |"])
    for finding in report["findings"]:
        lines.append(
            f"| {finding['severity']} | `{finding['code']}` | {finding['message']} | `{finding.get('path', '')}` |"
        )
    lines.append("")
    if summary["findings"] > summary["shown_findings"]:
        lines.append(f"_Showing {summary['shown_findings']} of {summary['findings']} findings (capped per code)._")
        lines.append("")
    return "\n".join(lines)
