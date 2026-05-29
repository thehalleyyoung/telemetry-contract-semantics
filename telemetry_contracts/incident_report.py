from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from .findings import Finding, has_at_least
from .scenario import check_scenario
from .semantics import build_event_structure, format_event_structure_markdown
from .validator import validate_events


def generate_incident_readiness_report(contract: dict[str, Any], events: list[dict[str, Any]], scenario_ids: list[str] | None = None) -> dict[str, Any]:
    scenarios = _selected_scenarios(contract, scenario_ids)
    runtime_findings = validate_events(contract, events)
    scenario_sections = [_scenario_section(contract, events, scenario) for scenario in scenarios]
    scenario_findings = [finding for section in scenario_sections for finding in section["raw_findings"]]
    findings = runtime_findings + scenario_findings
    finding_dicts = [finding.to_dict() for finding in findings]
    coverage = {
        "required_evidence": _required_evidence_coverage(contract, events),
        "temporal": _temporal_coverage(contract, findings),
        "correlation": _correlation_coverage(contract, findings),
        "privacy": _privacy_coverage(finding_dicts),
        "remediation": _remediation_coverage(finding_dicts),
    }
    event_structure = build_event_structure(events)
    score = _overall_score(coverage)
    return {
        "service": contract.get("service", ""),
        "owner": _owner(contract),
        "summary": {
            "incident_readiness_score": score,
            "pass": not has_at_least(findings, "error"),
            "events": len(events),
            "findings": len(findings),
            "findings_by_code": dict(sorted(Counter(item["code"] for item in finding_dicts).items())),
            "findings_by_category": dict(sorted(Counter(item.get("category", "uncategorized") for item in finding_dicts).items())),
            "findings_by_severity": dict(sorted(Counter(item["severity"] for item in finding_dicts).items())),
        },
        "coverage": coverage,
        "event_structure": {
            "model": event_structure["model"],
            "node_count": event_structure["node_count"],
            "edge_count": event_structure["edge_count"],
            "concurrency_pair_count": event_structure["concurrency_pair_count"],
            "nodes": event_structure["nodes"],
            "edges": event_structure["edges"],
            "concurrency": event_structure["concurrency"],
            "incident_windows": event_structure["incident_windows"],
            "diagrams": event_structure["diagrams"],
        },
        "unanswered_questions": [
            {
                "id": section["id"],
                "question": section["question"],
                "answerable": section["answerable"],
                "missing_evidence": section["missing_evidence"],
            }
            for section in scenario_sections
            if not section["answerable"]
        ],
        "top_remediations": _top_remediations(finding_dicts),
        "findings": finding_dicts,
        "limitations": [
            "Scores are computed from the supplied finite telemetry file and contract, not from production exhaustiveness.",
            "Historical case-study events are reconstructed fixtures when their metadata says so; findings bound answerability for this artifact only.",
        ],
    }


def format_incident_readiness_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Incident-readiness report: {report['service']}",
        "",
        f"- Owner: `{report.get('owner') or 'unknown'}`",
        f"- Score: `{summary['incident_readiness_score']}`",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Events: {summary['events']}",
        f"- Findings: {summary['findings']}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        "",
        "## Coverage",
        "",
        "| Area | Score | Passed | Failed | Notes |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    coverage = report["coverage"]
    for key, label in (
        ("required_evidence", "Required evidence"),
        ("temporal", "Temporal coverage"),
        ("correlation", "Correlation coverage"),
        ("privacy", "Privacy risk"),
        ("remediation", "Remediation completeness"),
    ):
        item = coverage[key]
        notes = item.get("risk_level") or item.get("notes") or ""
        lines.append(f"| {label} | {item['score']} | {item.get('passed', 0)} | {item.get('failed', 0)} | {notes} |")
    lines.extend(["", "## Unanswered incident questions", ""])
    if not report["unanswered_questions"]:
        lines.append("All declared incident questions are answerable from the supplied telemetry.")
    else:
        for question in report["unanswered_questions"]:
            lines.append(f"- `{question['id']}`: {question['question']}")
            for missing in question["missing_evidence"]:
                lines.append(f"  - Missing `{missing['code']}` at `{missing['path']}`: {missing['message']}")
    lines.extend(["", "## Top remediations", ""])
    if not report["top_remediations"]:
        lines.append("No remediation needed for the supplied telemetry.")
    else:
        for item in report["top_remediations"]:
            lines.append(f"- {item['count']}× `{item['code']}` ({item['severity']}, {item['category']}): {item['remediation']}")
    lines.extend(["", format_event_structure_markdown(report["event_structure"])])
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def _selected_scenarios(contract: dict[str, Any], scenario_ids: list[str] | None) -> list[dict[str, Any]]:
    scenarios = [scenario for scenario in contract.get("scenarios", []) or [] if isinstance(scenario, dict)]
    if not scenario_ids:
        return scenarios
    requested = set(scenario_ids)
    return [scenario for scenario in scenarios if scenario.get("id") in requested]


def _scenario_section(contract: dict[str, Any], events: list[dict[str, Any]], scenario: dict[str, Any]) -> dict[str, Any]:
    findings = check_scenario(contract, events, scenario)
    return {
        "id": scenario.get("id", ""),
        "question": scenario.get("question", ""),
        "answerable": not has_at_least(findings, "error"),
        "missing_evidence": [finding.to_dict() for finding in findings],
        "raw_findings": findings,
    }


def _owner(contract: dict[str, Any]) -> str:
    metadata = contract.get("metadata")
    if isinstance(metadata, dict):
        for key in ("owner", "service_owner", "team"):
            if isinstance(metadata.get(key), str):
                return metadata[key]
    return ""


def _required_evidence_coverage(contract: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    obligations = []
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for signal_index, spec in enumerate(contract.get(section, []) or []):
            if not isinstance(spec, dict) or not spec.get("required", True) or not isinstance(spec.get("name"), str):
                continue
            name = spec["name"]
            matches = [event for event in events if event.get("kind") == kind and event.get("name") == name]
            obligations.append((f"{kind}:{name}", bool(matches)))
            for field_name, field_spec in _field_specs(spec).items():
                if not isinstance(field_spec, dict) or not field_spec.get("required", True) or field_spec.get("transformation") == "omitted":
                    continue
                obligations.append((f"{kind}:{name}.{field_name}", any(_lookup(event, field_name)[0] is not _MISSING for event in matches)))
            if kind == "metric" and isinstance(spec.get("value"), dict) and spec["value"].get("required", True):
                obligations.append((f"metric:{name}.value", any("value" in event for event in matches)))
    passed = sum(1 for _, ok in obligations if ok)
    failed_items = [name for name, ok in obligations if not ok]
    return _score_section(passed, len(obligations) - passed, {"missing": failed_items[:25]})


def _temporal_coverage(contract: dict[str, Any], findings: list[Finding]) -> dict[str, Any]:
    total = len([item for item in contract.get("temporal_sequences", []) or [] if isinstance(item, dict) and item.get("required", True)])
    failed = len({finding.contract_path for finding in findings if finding.code.startswith("telemetry.temporal_")})
    passed = max(total - failed, 0)
    return _score_section(passed, failed, {"notes": "no temporal_sequences declared" if total == 0 else ""})


def _correlation_coverage(contract: dict[str, Any], findings: list[Finding]) -> dict[str, Any]:
    policy = contract.get("correlation")
    if not isinstance(policy, dict):
        return _score_section(0, 0, {"notes": "no correlation policy declared"})
    required = policy.get("require_on", ["spans", "logs"])
    total = len(required) if isinstance(required, list) else 1
    failed = 1 if any(finding.code.startswith("telemetry.correlation_") for finding in findings) else 0
    passed = max(total - failed, 0)
    return _score_section(passed, failed)


def _privacy_coverage(findings: list[dict[str, Any]]) -> dict[str, Any]:
    privacy = [finding for finding in findings if finding.get("category") == "privacy-security"]
    errors = [finding for finding in privacy if finding.get("severity") == "error"]
    warnings = [finding for finding in privacy if finding.get("severity") == "warning"]
    if errors:
        risk = "high"
        score = 0
    elif warnings:
        risk = "medium"
        score = 50
    else:
        risk = "none"
        score = 100
    return {"score": score, "passed": 0 if privacy else 1, "failed": len(privacy), "risk_level": risk}


def _remediation_coverage(findings: list[dict[str, Any]]) -> dict[str, Any]:
    if not findings:
        return {"score": 100, "passed": 0, "failed": 0, "notes": "no findings"}
    remediated = sum(1 for finding in findings if finding.get("remediation"))
    missing = len(findings) - remediated
    return _score_section(remediated, missing)


def _score_section(passed: int, failed: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    total = passed + failed
    score = 100 if total == 0 else round((passed / total) * 100)
    section = {"score": score, "passed": passed, "failed": failed}
    if extra:
        section.update(extra)
    return section


def _overall_score(coverage: dict[str, dict[str, Any]]) -> int:
    weights = {
        "required_evidence": 0.35,
        "temporal": 0.15,
        "correlation": 0.15,
        "privacy": 0.20,
        "remediation": 0.15,
    }
    return round(sum(coverage[key]["score"] * weight for key, weight in weights.items()))


def _top_remediations(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for finding in findings:
        key = (
            finding.get("severity", ""),
            finding.get("category", ""),
            finding.get("code", ""),
            finding.get("remediation", ""),
        )
        grouped[key] += 1
    items = [
        {
            "severity": severity,
            "category": category,
            "code": code,
            "remediation": remediation,
            "count": count,
        }
        for (severity, category, code, remediation), count in grouped.items()
    ]
    return sorted(items, key=lambda item: (-item["count"], item["severity"], item["code"]))[:10]


def _field_specs(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for container in ("fields", "attributes", "tags"):
        raw = spec.get(container, {}) or {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                merged[str(key)] = value if isinstance(value, dict) else {"type": str(value)}
    return merged


_MISSING = object()


def _lookup(event: dict[str, Any], field_name: str) -> tuple[Any, str]:
    for container in ("attributes", "tags", "fields"):
        values = event.get(container)
        if isinstance(values, dict) and field_name in values:
            return values[field_name], f"{container}.{field_name}"
    if field_name in event:
        return event[field_name], field_name
    return _MISSING, field_name
