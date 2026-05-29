from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .findings import Finding, has_at_least
from .scenario import evaluate_scenario_adequacy
from .validator import validate_events

SUPPORTED_TRANSFORMATIONS = {
    "redaction",
    "redact",
    "redacted",
    "hashing",
    "hash",
    "hashed",
    "tokenization",
    "tokenize",
    "tokenized",
    "bucketing",
    "bucket",
    "bucketed",
    "omission",
    "omit",
    "omitted",
    "sampling",
    "sample",
    "retention",
    "aggregation",
    "aggregate",
    "routing",
    "route",
}

CANONICAL_TRANSFORMATIONS = {
    "redact": "redaction",
    "redacted": "redaction",
    "hash": "hashing",
    "hashed": "hashing",
    "tokenize": "tokenization",
    "tokenized": "tokenization",
    "bucket": "bucketing",
    "bucketed": "bucketing",
    "omit": "omission",
    "omitted": "omission",
    "sample": "sampling",
    "aggregate": "aggregation",
    "route": "routing",
}

PRESERVATION_MODEL = {
    "name": "transformation-preservation-v1",
    "relation": (
        "For a contract C, source trace T, transformed trace T′, and approved transformations Δ, "
        "T′ preserves C when every runtime contract obligation and diagnosability witness that is "
        "satisfied in T remains satisfied in T′. The check is obligation-local: it reports newly "
        "destroyed evidence even when T already violates unrelated obligations."
    ),
    "supported_transformations": sorted({CANONICAL_TRANSFORMATIONS.get(item, item) for item in SUPPORTED_TRANSFORMATIONS}),
}


def check_transformation_preservation(
    contract: dict[str, Any],
    source_events: list[dict[str, Any]],
    transformed_events: list[dict[str, Any]],
    transformations: list[str] | None = None,
    scenario_ids: list[str] | None = None,
) -> dict[str, Any]:
    approved = _approved_transformations(contract, transformations)
    scenarios = _selected_scenarios(contract, scenario_ids)
    source_findings = validate_events(contract, source_events)
    transformed_findings = validate_events(contract, transformed_events)
    findings = _new_runtime_obligation_findings(source_findings, transformed_findings)
    findings.extend(_scenario_preservation_findings(contract, source_events, transformed_events, scenarios))
    finding_dicts = [finding.to_dict() for finding in findings]
    return {
        "model": PRESERVATION_MODEL,
        "service": contract.get("service", ""),
        "approved_transformations": approved,
        "summary": {
            "pass": not has_at_least(findings, "error"),
            "source_events": len(source_events),
            "transformed_events": len(transformed_events),
            "events_removed": max(0, len(source_events) - len(transformed_events)),
            "scenarios_checked": len(scenarios),
            "preservation_findings": len(findings),
            "source_findings": len(source_findings),
            "transformed_findings": len(transformed_findings),
            "findings_by_code": dict(sorted(Counter(item["code"] for item in finding_dicts).items())),
            "findings_by_severity": dict(sorted(Counter(item["severity"] for item in finding_dicts).items())),
        },
        "findings": finding_dicts,
        "source_findings": [finding.to_dict() for finding in source_findings],
        "transformed_findings": [finding.to_dict() for finding in transformed_findings],
        "scenarios": [_scenario_summary(contract, source_events, transformed_events, scenario) for scenario in scenarios],
        "limitations": [
            "The relation is scoped to this contract's declared signals, field predicates, privacy transformations, and selected scenarios.",
            "The checker compares finite artifacts; it does not prove a collector implementation correct for all possible production traces.",
            "Historical case-study fixtures are reconstructed when their metadata says so; preservation claims are bounded to checked-in artifacts.",
        ],
    }


def format_preservation_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Transformation-preservation report: {report.get('service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Preserves selected obligations: `{str(summary['pass']).lower()}`",
        f"- Approved transformations: `{', '.join(report.get('approved_transformations') or ['unspecified'])}`",
        f"- Source events: {summary['source_events']}",
        f"- Transformed events: {summary['transformed_events']}",
        f"- Events removed: {summary['events_removed']}",
        f"- Scenarios checked: {summary['scenarios_checked']}",
        f"- Preservation findings: {summary['preservation_findings']}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        "",
        "## Relation",
        "",
        report["model"]["relation"],
        "",
        "## Preservation findings",
        "",
    ]
    if not report["findings"]:
        lines.append("No preservation regressions were found for selected obligations.")
    else:
        for finding in report["findings"]:
            lines.append(f"- **{finding['severity']} `{finding['code']}`** at `{finding['path']}`: {finding['message']}")
            if finding.get("details"):
                lines.append(f"  - Details: `{json.dumps(finding['details'], sort_keys=True)}`")
    lines.extend(["", "## Scenario preservation", ""])
    if not report.get("scenarios"):
        lines.append("No scenarios were selected.")
    for scenario in report.get("scenarios", []):
        lines.extend(
            [
                f"### `{scenario['id']}`",
                "",
                f"- Source answerable: `{str(scenario['source_answerable']).lower()}`",
                f"- Transformed answerable: `{str(scenario['transformed_answerable']).lower()}`",
                f"- Lost witnesses: {len(scenario['lost_witnesses'])}",
            ]
        )
        for witness in scenario["lost_witnesses"]:
            lines.append(f"  - `{witness['requirement']}` lost `{witness['field']}` ({witness['source']} → {witness['transformed']})")
        lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def _approved_transformations(contract: dict[str, Any], requested: list[str] | None) -> list[str]:
    raw = requested or []
    if not raw:
        metadata = contract.get("metadata") if isinstance(contract.get("metadata"), dict) else {}
        policy = metadata.get("transformation_preservation") if isinstance(metadata, dict) else None
        if isinstance(policy, dict) and isinstance(policy.get("approved_transformations"), list):
            raw = [str(item) for item in policy["approved_transformations"]]
    approved = []
    for item in raw:
        key = str(item).strip().lower().replace("_", "-")
        normalized = key.replace("-", "_")
        canonical = CANONICAL_TRANSFORMATIONS.get(key) or CANONICAL_TRANSFORMATIONS.get(normalized) or key
        canonical = canonical.replace("_", "-")
        if canonical not in {name.replace("_", "-") for name in PRESERVATION_MODEL["supported_transformations"]}:
            raise ValueError(f"unsupported transformation {item!r}; supported: {', '.join(PRESERVATION_MODEL['supported_transformations'])}")
        approved.append(canonical)
    return sorted(set(approved))


def _selected_scenarios(contract: dict[str, Any], scenario_ids: list[str] | None) -> list[dict[str, Any]]:
    scenarios = [scenario for scenario in contract.get("scenarios", []) or [] if isinstance(scenario, dict)]
    requested = scenario_ids or []
    if not requested:
        metadata = contract.get("metadata") if isinstance(contract.get("metadata"), dict) else {}
        policy = metadata.get("transformation_preservation") if isinstance(metadata, dict) else None
        if isinstance(policy, dict) and isinstance(policy.get("preserve_scenarios"), list):
            requested = [str(item) for item in policy["preserve_scenarios"]]
    if not requested:
        return scenarios
    selected = set(requested)
    return [scenario for scenario in scenarios if scenario.get("id") in selected]


def _new_runtime_obligation_findings(source_findings: list[Finding], transformed_findings: list[Finding]) -> list[Finding]:
    source_keys = {_runtime_key(finding) for finding in source_findings}
    findings: list[Finding] = []
    for finding in transformed_findings:
        if _runtime_key(finding) in source_keys:
            continue
        if not finding.code.startswith("telemetry."):
            continue
        findings.append(
            Finding(
                finding.severity,
                "preservation.contract_obligation",
                f"transformation introduced {finding.code}: {finding.message}",
                finding.path,
                finding.contract_path,
                finding.event_index,
                {"introduced_finding": finding.to_dict()},
            )
        )
    return findings


def _runtime_key(finding: Finding) -> tuple[str, str | None, str]:
    return (finding.code, finding.contract_path, finding.message)


def _scenario_preservation_findings(
    contract: dict[str, Any],
    source_events: list[dict[str, Any]],
    transformed_events: list[dict[str, Any]],
    scenarios: list[dict[str, Any]],
) -> list[Finding]:
    findings: list[Finding] = []
    for scenario in scenarios:
        source = evaluate_scenario_adequacy(contract, source_events, scenario)
        transformed = evaluate_scenario_adequacy(contract, transformed_events, scenario)
        for lost in _lost_witnesses(source, transformed):
            code = "preservation.scenario_signal" if lost["field"] == "$signal" else "preservation.scenario_field"
            findings.append(
                Finding(
                    "error",
                    code,
                    f"transformation removed diagnosability witness {lost['field']} for {lost['requirement']} in scenario '{scenario.get('id', '')}'",
                    lost["path"],
                    lost["contract_path"],
                    details={"scenario": scenario.get("id", ""), "source": lost["source"], "transformed": lost["transformed"]},
                )
            )
    return findings


def _scenario_summary(contract: dict[str, Any], source_events: list[dict[str, Any]], transformed_events: list[dict[str, Any]], scenario: dict[str, Any]) -> dict[str, Any]:
    source = evaluate_scenario_adequacy(contract, source_events, scenario)
    transformed = evaluate_scenario_adequacy(contract, transformed_events, scenario)
    return {
        "id": scenario.get("id", ""),
        "question": scenario.get("question", ""),
        "source_answerable": source["answerable"],
        "transformed_answerable": transformed["answerable"],
        "lost_witnesses": _lost_witnesses(source, transformed),
    }


def _lost_witnesses(source: dict[str, Any], transformed: dict[str, Any]) -> list[dict[str, str]]:
    source_obs = {_obs_key(item): item for item in source.get("minimum_observations", [])}
    transformed_obs = {_obs_key(item): item for item in transformed.get("minimum_observations", [])}
    lost: list[dict[str, str]] = []
    for requirement in sorted(source_obs):
        before = source_obs[requirement]
        after = transformed_obs.get(requirement, {})
        before_signal = bool(before.get("matching_event_indices"))
        after_signal = bool(after.get("matching_event_indices"))
        if before_signal and not after_signal:
            lost.append(
                {
                    "requirement": requirement,
                    "field": "$signal",
                    "source": "present",
                    "transformed": "missing",
                    "path": str(before.get("evidence_path", f"events[{requirement}]")),
                    "contract_path": str(before.get("contract_path", "$.scenarios")),
                }
            )
        before_fields = set(str(field) for field in before.get("observed_fields", []))
        after_fields = set(str(field) for field in after.get("observed_fields", []))
        for field in sorted(before_fields - after_fields):
            lost.append(
                {
                    "requirement": requirement,
                    "field": field,
                    "source": "present",
                    "transformed": "missing",
                    "path": f"{before.get('evidence_path', f'events[{requirement}]')}.{field}",
                    "contract_path": f"{before.get('contract_path', '$.scenarios')}.fields",
                }
            )
    return lost


def _obs_key(observation: dict[str, Any]) -> str:
    return f"{observation.get('signal', '')}:{observation.get('name', '')}"
