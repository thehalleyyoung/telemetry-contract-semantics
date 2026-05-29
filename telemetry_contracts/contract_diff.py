from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .findings import Finding


CONTRACT_DIFF_MODEL = {
    "name": "contract-diff-pr-v1",
    "purpose": "Summarize contract changes that matter during pull-request review.",
    "focus": [
        "new required telemetry obligations",
        "removed required telemetry obligations",
        "changed privacy classifications or transformations",
        "changed diagnosability claims",
    ],
}


def generate_contract_diff_report(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    base_obligations = _obligations(base)
    candidate_obligations = _obligations(candidate)
    new_obligations = _diff_added(base_obligations, candidate_obligations, "contract_diff.new_obligation", "info")
    removed_obligations = _diff_removed(base_obligations, candidate_obligations, "contract_diff.removed_obligation", "warning")
    changed_privacy = _changed_privacy(base, candidate)
    changed_claims = _changed_diagnosability_claims(base, candidate)
    findings = new_obligations + removed_obligations + changed_privacy + changed_claims
    finding_dicts = [finding.to_dict() for finding in findings]
    return {
        "model": CONTRACT_DIFF_MODEL,
        "base_service": base.get("service", ""),
        "candidate_service": candidate.get("service", ""),
        "summary": {
            "new_obligations": len(new_obligations),
            "removed_obligations": len(removed_obligations),
            "changed_privacy_classifications": len(changed_privacy),
            "changed_diagnosability_claims": len(changed_claims),
            "findings": len(findings),
            "findings_by_code": dict(sorted(Counter(item["code"] for item in finding_dicts).items())),
            "pr_attention_required": bool(removed_obligations or changed_privacy or changed_claims),
        },
        "sections": {
            "new_obligations": [finding.to_dict() for finding in new_obligations],
            "removed_obligations": [finding.to_dict() for finding in removed_obligations],
            "changed_privacy_classifications": [finding.to_dict() for finding in changed_privacy],
            "changed_diagnosability_claims": [finding.to_dict() for finding in changed_claims],
        },
        "findings": finding_dicts,
        "limitations": [
            "The report compares two finite JSON contracts and does not inspect source-code diffs.",
            "Predicate meaning is summarized structurally; regex or prose implication is not proved.",
            "The report is designed for pull-request review triage; use refinement and validation commands for gate-specific checks.",
        ],
    }


def format_contract_diff_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Contract-diff PR report: {report.get('candidate_service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Base service: `{report.get('base_service', '')}`",
        f"- Candidate service: `{report.get('candidate_service', '')}`",
        f"- New obligations: {summary['new_obligations']}",
        f"- Removed obligations: {summary['removed_obligations']}",
        f"- Changed privacy classifications: {summary['changed_privacy_classifications']}",
        f"- Changed diagnosability claims: {summary['changed_diagnosability_claims']}",
        f"- PR attention required: `{str(summary['pr_attention_required']).lower()}`",
        "",
        "## Pull-request review focus",
        "",
    ]
    lines.extend(f"- {item}" for item in report["model"]["focus"])
    for key, title in (
        ("new_obligations", "New obligations"),
        ("removed_obligations", "Removed obligations"),
        ("changed_privacy_classifications", "Changed privacy classifications"),
        ("changed_diagnosability_claims", "Changed diagnosability claims"),
    ):
        lines.extend(["", f"## {title}", ""])
        findings = report["sections"][key]
        if not findings:
            lines.append("None.")
            continue
        lines.extend(["| Severity | Path | Message | Details |", "| --- | --- | --- | --- |"])
        for finding in findings:
            lines.append(
                f"| {_md(finding['severity'])} | `{_md(finding['path'])}` | {_md(finding['message'])} | "
                f"`{_md(json.dumps(finding.get('details', {}), sort_keys=True))}` |"
            )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines).rstrip()


def _diff_added(base: dict[str, dict[str, Any]], candidate: dict[str, dict[str, Any]], code: str, severity: str) -> list[Finding]:
    findings = []
    for key in sorted(set(candidate) - set(base)):
        item = candidate[key]
        findings.append(
            Finding(
                severity,  # type: ignore[arg-type]
                code,
                f"candidate adds {item['label']}",
                item["path"],
                item["path"],
                details={"kind": item["kind"], "id": item["id"], "fingerprint": key},
            )
        )
    return findings


def _diff_removed(base: dict[str, dict[str, Any]], candidate: dict[str, dict[str, Any]], code: str, severity: str) -> list[Finding]:
    findings = []
    for key in sorted(set(base) - set(candidate)):
        item = base[key]
        findings.append(
            Finding(
                severity,  # type: ignore[arg-type]
                code,
                f"candidate removes {item['label']}",
                item["path"],
                item["path"],
                details={"kind": item["kind"], "id": item["id"], "fingerprint": key},
            )
        )
    return findings


def _obligations(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    obligations: dict[str, dict[str, Any]] = {}
    for section in ("spans", "metrics", "logs"):
        for signal in _list_dicts(contract.get(section)):
            name = signal.get("name")
            if not isinstance(name, str):
                continue
            kind = section[:-1]
            if signal.get("required", True):
                _add_obligation(obligations, "required_signal", f"{kind}:{name}", f"required {kind} `{name}`", f"$.{section}[name={name!r}]")
            for field_name, field in _fields_by_name(signal, include_value=section == "metrics").items():
                if field.get("required", field_name == "value"):
                    _add_obligation(
                        obligations,
                        "required_field",
                        f"{kind}:{name}:{field_name}",
                        f"required field `{field_name}` on {kind} `{name}`",
                        f"$.{section}[name={name!r}].fields.{field_name}",
                    )
    for scenario in _list_dicts(contract.get("scenarios")):
        scenario_id = scenario.get("id")
        if isinstance(scenario_id, str):
            _add_obligation(obligations, "scenario", scenario_id, f"diagnosability scenario `{scenario_id}`", f"$.scenarios[id={scenario_id!r}]")
            for idx, requirement in enumerate(_list_dicts(scenario.get("requires"))):
                _add_obligation(
                    obligations,
                    "scenario_requirement",
                    f"{scenario_id}:{_stable_json(requirement)}",
                    f"scenario `{scenario_id}` evidence requirement",
                    f"$.scenarios[id={scenario_id!r}].requires[{idx}]",
                )
    for section, label in (
        ("temporal_properties", "temporal property"),
        ("alternative_obligations", "alternative obligation"),
    ):
        for item in _list_dicts(contract.get(section)):
            item_id = item.get("id")
            if isinstance(item_id, str):
                _add_obligation(obligations, section[:-1], item_id, f"{label} `{item_id}`", f"$.{section}[id={item_id!r}]")
    ag = contract.get("assume_guarantee") if isinstance(contract.get("assume_guarantee"), dict) else {}
    for layer in ("service_guarantees", "collector_assumptions", "environment_assumptions", "oncall_obligations"):
        for idx, item in enumerate(_list_dicts(ag.get(layer))):
            item_id = str(item.get("id") or _stable_json(item))
            _add_obligation(obligations, f"assume_guarantee.{layer}", item_id, f"{layer.replace('_', ' ')} `{item_id}`", f"$.assume_guarantee.{layer}[{idx}]")
    return obligations


def _add_obligation(result: dict[str, dict[str, Any]], kind: str, item_id: str, label: str, path: str) -> None:
    key = f"{kind}:{item_id}"
    result[key] = {"kind": kind, "id": item_id, "label": label, "path": path}


def _changed_privacy(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    base_classes = base.get("privacy_classifications") if isinstance(base.get("privacy_classifications"), dict) else {}
    candidate_classes = candidate.get("privacy_classifications") if isinstance(candidate.get("privacy_classifications"), dict) else {}
    for name in sorted(set(base_classes) | set(candidate_classes)):
        base_value = base_classes.get(name)
        candidate_value = candidate_classes.get(name)
        if _stable_json(base_value) != _stable_json(candidate_value):
            path = f"$.privacy_classifications.{name}"
            findings.append(
                Finding(
                    "warning",
                    "contract_diff.privacy_changed",
                    f"privacy classification `{name}` changed",
                    path,
                    path,
                    details={"base": base_value, "candidate": candidate_value},
                )
            )
    base_privacy_fields = _privacy_fields(base)
    candidate_privacy_fields = _privacy_fields(candidate)
    for key in sorted(set(base_privacy_fields) | set(candidate_privacy_fields)):
        base_field = base_privacy_fields.get(key)
        candidate_field = candidate_privacy_fields.get(key)
        base_privacy = base_field["privacy"] if base_field else None
        candidate_privacy = candidate_field["privacy"] if candidate_field else None
        if base_privacy != candidate_privacy:
            field = candidate_field or base_field
            findings.append(
                Finding(
                    "warning",
                    "contract_diff.privacy_changed",
                    f"field privacy metadata changed for {field['label']}",
                    field["path"],
                    field["path"],
                    details={"base": base_privacy, "candidate": candidate_privacy},
                )
            )
    return findings


def _privacy_fields(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fields = {}
    for section in ("spans", "metrics", "logs"):
        for signal in _list_dicts(contract.get(section)):
            name = signal.get("name")
            if not isinstance(name, str):
                continue
            for field_name, field in _fields_by_name(signal, include_value=section == "metrics").items():
                privacy = {key: field.get(key) for key in ("classification", "sensitivity", "privacy_classification", "transformation", "pii", "allow_raw_sensitive") if key in field}
                if privacy:
                    key = f"{section}:{name}:{field_name}"
                    fields[key] = {
                        "path": f"$.{section}[name={name!r}].fields.{field_name}",
                        "label": f"`{field_name}` on {section[:-1]} `{name}`",
                        "privacy": privacy,
                    }
    return fields


def _changed_diagnosability_claims(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for section, label in (
        ("scenarios", "scenario"),
        ("temporal_properties", "temporal property"),
        ("alternative_obligations", "alternative obligation"),
    ):
        base_items = _by_id(base.get(section))
        candidate_items = _by_id(candidate.get(section))
        for item_id in sorted(set(base_items) & set(candidate_items)):
            if _stable_json(base_items[item_id]) != _stable_json(candidate_items[item_id]):
                path = f"$.{section}[id={item_id!r}]"
                findings.append(
                    Finding(
                        "warning",
                        "contract_diff.diagnosability_claim_changed",
                        f"{label} `{item_id}` changed",
                        path,
                        path,
                        details={"base": base_items[item_id], "candidate": candidate_items[item_id]},
                    )
                )
    base_policy = _transformation_policy(base)
    candidate_policy = _transformation_policy(candidate)
    for key in ("claim", "preserve_scenarios"):
        if _stable_json(base_policy.get(key)) != _stable_json(candidate_policy.get(key)):
            path = f"$.metadata.transformation_preservation.{key}"
            findings.append(
                Finding(
                    "warning",
                    "contract_diff.diagnosability_claim_changed",
                    f"transformation-preservation diagnosability `{key}` changed",
                    path,
                    path,
                    details={"base": base_policy.get(key), "candidate": candidate_policy.get(key)},
                )
            )
    return findings


def _fields_by_name(spec: dict[str, Any], *, include_value: bool) -> dict[str, dict[str, Any]]:
    fields: dict[str, dict[str, Any]] = {}
    if include_value and isinstance(spec.get("value"), dict):
        fields["value"] = spec["value"]
    for container in ("fields", "attributes", "tags"):
        raw = spec.get(container, {}) or {}
        if isinstance(raw, dict):
            for name, field in raw.items():
                if isinstance(field, dict):
                    fields[str(name)] = field
    return fields


def _by_id(items: Any) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in _list_dicts(items) if isinstance(item.get("id"), str)}


def _list_dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _transformation_policy(contract: dict[str, Any]) -> dict[str, Any]:
    metadata = contract.get("metadata") if isinstance(contract.get("metadata"), dict) else {}
    policy = metadata.get("transformation_preservation")
    return policy if isinstance(policy, dict) else {}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
