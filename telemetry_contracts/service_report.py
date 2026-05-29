from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .findings import Finding, TAXONOMY, has_at_least
from .incident_report import generate_incident_readiness_report
from .semconv import lint_semantic_conventions
from .static_checker import check_sources
from .validator import validate_events


def generate_service_owner_report(contract: dict[str, Any], events: list[dict[str, Any]], sources: list[str | Path] | None = None, scenario_ids: list[str] | None = None) -> dict[str, Any]:
    runtime = [finding.to_dict() for finding in validate_events(contract, events, strict=True)]
    static = [finding.to_dict() for finding in check_sources(contract, sources or [])] if sources else []
    semconv = lint_semantic_conventions(contract, events).get("findings", [])
    readiness = generate_incident_readiness_report(contract, events, scenario_ids)
    findings = _dedupe_findings(runtime + static + semconv + readiness.get("findings", []))
    owner = _owner(contract)
    return {
        "tool": "telemetry-contracts-service-owner-report-v1",
        "service": contract.get("service", ""),
        "owner": owner,
        "summary": {
            "pass": not has_at_least([_finding(item) for item in findings], "error"),
            "events": len(events),
            "sources": len(sources or []),
            "findings": len(findings),
            "findings_by_code": dict(sorted(Counter(item.get("code") for item in findings).items())),
            "findings_by_severity": dict(sorted(Counter(item.get("severity") for item in findings).items())),
            "incident_readiness_score": readiness["summary"]["incident_readiness_score"],
        },
        "contract_coverage": _coverage(contract, events),
        "failing_obligations": _failing_obligations(findings),
        "privacy_risks": [item for item in findings if item.get("category") == "privacy-security"],
        "collector_export_problems": [item for item in findings if str(item.get("code", "")).startswith(("otlp.", "semconv.")) or "collector" in str(item.get("message", "")).lower()],
        "remediation_priority": _remediation_priority(findings),
        "source_spans": _source_spans(findings),
        "readiness": {"coverage": readiness["coverage"], "unanswered_questions": readiness["unanswered_questions"]},
        "findings": findings,
        "limitations": [
            "Report summarizes supplied finite artifacts only; absence of findings is not a production guarantee.",
            "Static source links are limited to checked files and lightweight source extraction.",
        ],
    }


def format_service_owner_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Service-owner telemetry report: {report['service']}",
        "",
        f"- Owner: `{report.get('owner') or 'unknown'}`",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Incident-readiness score: `{summary['incident_readiness_score']}`",
        f"- Events: {summary['events']}",
        f"- Sources: {summary['sources']}",
        f"- Findings: {summary['findings']}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        "",
        "## Contract coverage",
        "",
        "| Kind | Required | Observed | Missing |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in report["contract_coverage"]:
        lines.append(f"| {item['kind']} | {item['required']} | {item['observed']} | {', '.join(item['missing']) or 'none'} |")
    lines.extend(["", "## Failing obligations", ""])
    if not report["failing_obligations"]:
        lines.append("No failing obligations in the supplied artifacts.")
    else:
        for item in report["failing_obligations"][:25]:
            lines.append(f"- `{item['code']}` ({item['severity']}) at `{item.get('path') or item.get('contract_path') or 'n/a'}`: {item['message']}")
    lines.extend(["", "## Privacy risks", ""])
    if not report["privacy_risks"]:
        lines.append("No privacy/security findings in the supplied artifacts.")
    else:
        for item in report["privacy_risks"][:25]:
            lines.append(f"- `{item['code']}` ({item['severity']}): {item['message']}")
    lines.extend(["", "## Remediation priority", "", "| Severity | Category | Owner | Count | Remediation |", "| --- | --- | --- | ---: | --- |"])
    for item in report["remediation_priority"]:
        lines.append(f"| {item['severity']} | {item['category']} | {item['owner']} | {item['count']} | {item['remediation']} |")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.get("limitations", []))
    lines.append("")
    return "\n".join(lines)


def _owner(contract: dict[str, Any]) -> str:
    metadata = contract.get("metadata") if isinstance(contract.get("metadata"), dict) else {}
    return str(metadata.get("owner") or metadata.get("service_owner") or metadata.get("team") or "")


def _coverage(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        required = [item.get("name") for item in contract.get(section, []) if isinstance(item, dict) and item.get("required", True) and item.get("name")]
        observed = {event.get("name") for event in events if event.get("kind") == kind}
        rows.append({"kind": kind, "required": len(required), "observed": len(set(required) & observed), "missing": sorted(set(required) - observed)})
    return rows


def _failing_obligations(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in findings if item.get("severity") in {"error", "warning"}]


def _dedupe_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for item in findings:
        key = (item.get("code"), item.get("severity"), item.get("message"), item.get("path"), item.get("contract_path"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _remediation_priority(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for item in findings:
        code = str(item.get("code", ""))
        taxonomy = TAXONOMY.get(code, {})
        key = (str(item.get("severity", taxonomy.get("default_severity", "warning"))), str(item.get("category", taxonomy.get("category", "uncategorized"))), str(item.get("service_owner", taxonomy.get("service_owner", "contract service owner"))), str(item.get("remediation", taxonomy.get("remediation", "Inspect the finding."))))
        grouped[key] += 1
    rank = {"error": 0, "warning": 1, "info": 2}
    rows = [{"severity": k[0], "category": k[1], "owner": k[2], "remediation": k[3], "count": count} for k, count in grouped.items()]
    return sorted(rows, key=lambda item: (rank.get(item["severity"], 9), -item["count"], item["category"]))[:10]


def _source_spans(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans = []
    for item in findings:
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        span = details.get("source_span")
        if isinstance(span, dict):
            spans.append({"code": item.get("code"), "source_span": span, "path": item.get("path")})
    return spans


def _finding(item: dict[str, Any]) -> Finding:
    return Finding(str(item.get("severity", "warning")), str(item.get("code", "unknown")), str(item.get("message", "")), str(item.get("path", "")))
