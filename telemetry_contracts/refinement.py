from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .findings import Finding, has_at_least
from .validator import SEVERITY_RANKS, _strict_enabled, validate_contract_shape


REFINEMENT_MODEL = {
    "name": "contract-refinement-v1",
    "notation": "C′ ⊑ C",
    "relation": (
        "A candidate contract C′ refines a base contract C when every base evidence "
        "obligation remains required by C′, predicate changes are strengthening or "
        "compatible, privacy and transformation policies are not weakened, and "
        "collector/environment/on-call assumptions are not made harder to satisfy."
    ),
    "clauses": [
        "REF.requirement-preservation",
        "REF.privacy-nonweakening",
        "REF.assumption-compatibility",
    ],
}


def check_contract_refinement(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    findings: list[Finding] = []
    findings.extend(_shape_findings(base, "base"))
    findings.extend(_shape_findings(candidate, "candidate"))
    findings.extend(_service_findings(base, candidate))
    findings.extend(_signal_requirement_findings(base, candidate))
    findings.extend(_scenario_and_temporal_findings(base, candidate))
    findings.extend(_privacy_policy_findings(base, candidate))
    findings.extend(_transformation_policy_findings(base, candidate))
    findings.extend(_strict_policy_findings(base, candidate))
    findings.extend(_assume_guarantee_findings(base, candidate))
    finding_dicts = [finding.to_dict() for finding in findings]
    return {
        "model": REFINEMENT_MODEL,
        "base_service": base.get("service", ""),
        "candidate_service": candidate.get("service", ""),
        "summary": {
            "refines": not has_at_least(findings, "error"),
            "findings": len(findings),
            "findings_by_code": dict(sorted(Counter(item["code"] for item in finding_dicts).items())),
            "findings_by_clause": dict(sorted(Counter(item.get("formal_clause", "") for item in finding_dicts).items())),
            "base_required_signals": len(_required_signals(base)),
            "candidate_required_signals": len(_required_signals(candidate)),
            "base_scenarios": len(_by_id(base.get("scenarios")).keys()),
            "candidate_scenarios": len(_by_id(candidate.get("scenarios")).keys()),
        },
        "findings": finding_dicts,
        "evidence": {
            "required_signals_preserved": _preserved_required_signals(base, candidate),
            "scenario_ids": _id_comparison(base.get("scenarios"), candidate.get("scenarios")),
            "temporal_property_ids": _id_comparison(base.get("temporal_properties"), candidate.get("temporal_properties")),
            "alternative_obligation_ids": _id_comparison(base.get("alternative_obligations"), candidate.get("alternative_obligations")),
        },
        "limitations": [
            "The checker is a deterministic finite-contract comparison, not a theorem prover over all possible future contract languages.",
            "Regex implication and arbitrary predicate implication are conservative: missing inherited predicates are reported, but stronger non-identical regexes are not proved equivalent.",
            "Historical case-study refinement reports compare checked-in reconstructed contract artifacts, not private production policy evolution.",
        ],
    }


def format_refinement_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Contract-refinement report: {report.get('candidate_service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Notation: `{report['model']['notation']}`",
        f"- Candidate refines base: `{str(summary['refines']).lower()}`",
        f"- Base service: `{report.get('base_service', '')}`",
        f"- Candidate service: `{report.get('candidate_service', '')}`",
        f"- Findings: {summary['findings']}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        f"- Findings by clause: `{json.dumps(summary['findings_by_clause'], sort_keys=True)}`",
        "",
        "## Relation",
        "",
        report["model"]["relation"],
        "",
        "## Findings",
        "",
    ]
    if not report["findings"]:
        lines.append("No refinement violations were found.")
    for finding in report["findings"]:
        lines.append(f"- **{finding['severity']} `{finding['code']}`** at `{finding['path']}`: {finding['message']}")
        if finding.get("details"):
            lines.append(f"  - Details: `{json.dumps(finding['details'], sort_keys=True)}`")
    evidence = report.get("evidence", {})
    lines.extend(
        [
            "",
            "## Evidence summary",
            "",
            f"- Required signals preserved: {len(evidence.get('required_signals_preserved', []))}",
            f"- Scenario IDs: `{json.dumps(evidence.get('scenario_ids', {}), sort_keys=True)}`",
            f"- Temporal property IDs: `{json.dumps(evidence.get('temporal_property_ids', {}), sort_keys=True)}`",
            f"- Alternative obligation IDs: `{json.dumps(evidence.get('alternative_obligation_ids', {}), sort_keys=True)}`",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines).rstrip()


def _shape_findings(contract: dict[str, Any], side: str) -> list[Finding]:
    findings = []
    for finding in validate_contract_shape(contract):
        findings.append(
            Finding(
                finding.severity,
                "refinement.malformed_contract",
                f"{side} contract is not well formed: {finding.message}",
                f"{side}:{finding.path}",
                finding.contract_path,
                details={"side": side, "source_finding": finding.to_dict()},
            )
        )
    return findings


def _service_findings(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    base_service = base.get("service")
    candidate_service = candidate.get("service")
    scope = _metadata(base).get("refinement_scope")
    if base_service in {"*", "organization", "team"} or scope in {"organization", "team", "fleet"}:
        return []
    if base_service and candidate_service and base_service != candidate_service:
        return [
            Finding(
                "error",
                "refinement.service_mismatch",
                f"candidate service {candidate_service!r} does not refine base service {base_service!r}",
                "$.service",
                "$.service",
            )
        ]
    return []


def _signal_requirement_findings(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    candidate_signals = _signals_by_key(candidate)
    for key, base_spec in _signals_by_key(base).items():
        section, name = key
        if not base_spec.get("required", True):
            continue
        candidate_spec = candidate_signals.get(key)
        signal_path = f"$.{section}[name={name!r}]"
        if not candidate_spec:
            findings.append(Finding("error", "refinement.required_signal_removed", f"candidate removed required {section[:-1]} {name!r}", signal_path, signal_path))
            continue
        if candidate_spec.get("required") is False:
            findings.append(Finding("error", "refinement.required_signal_removed", f"candidate made required {section[:-1]} {name!r} optional", signal_path, signal_path))
        findings.extend(_field_requirement_findings(section, name, base_spec, candidate_spec))
        if section == "logs":
            findings.extend(_log_policy_findings(name, base_spec, candidate_spec))
    return findings


def _field_requirement_findings(section: str, signal_name: str, base_spec: dict[str, Any], candidate_spec: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    base_fields = _fields_by_name(base_spec, include_value=section == "metrics")
    candidate_fields = _fields_by_name(candidate_spec, include_value=section == "metrics")
    for field_name, base_field in base_fields.items():
        candidate_field = candidate_fields.get(field_name)
        base_required = base_field.get("required", field_name == "value")
        path = f"$.{section}[name={signal_name!r}].fields.{field_name}"
        if candidate_field is None:
            if base_required:
                findings.append(Finding("error", "refinement.required_field_removed", f"candidate removed required field {field_name!r} from {signal_name!r}", path, path))
            continue
        if base_required and candidate_field.get("required") is False:
            findings.append(Finding("error", "refinement.required_field_removed", f"candidate made required field {field_name!r} optional on {signal_name!r}", path, path))
        findings.extend(_field_predicate_findings(path, base_field, candidate_field))
        findings.extend(_field_privacy_findings(path, field_name, base_field, candidate_field))
    return findings


def _field_predicate_findings(path: str, base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if base.get("type") and not _type_refines(str(base.get("type")), candidate.get("type")):
        findings.append(
            Finding(
                "error",
                "refinement.field_predicate_weakened",
                f"candidate type {candidate.get('type')!r} does not refine base type {base.get('type')!r}",
                path,
                path,
                details={"predicate": "type", "base": base.get("type"), "candidate": candidate.get("type")},
            )
        )
    if "allowed_values" in base and not _candidate_values_subset(base.get("allowed_values"), candidate.get("allowed_values")):
        findings.append(_predicate_finding(path, "allowed_values", base.get("allowed_values"), candidate.get("allowed_values")))
    for bound, direction in (("min", "lower"), ("max", "upper")):
        if bound in base and not _bound_refines(bound, base.get(bound), candidate.get(bound)):
            findings.append(_predicate_finding(path, f"{direction}_bound", base.get(bound), candidate.get(bound)))
    for regex_key in ("pattern", "message_pattern"):
        if regex_key in base and candidate.get(regex_key) != base.get(regex_key):
            findings.append(_predicate_finding(path, regex_key, base.get(regex_key), candidate.get(regex_key)))
    if "forbidden_patterns" in base and not _candidate_superset(_as_set(candidate.get("forbidden_patterns")), _as_set(base.get("forbidden_patterns"))):
        findings.append(_predicate_finding(path, "forbidden_patterns", base.get("forbidden_patterns"), candidate.get("forbidden_patterns")))
    if "unit" in base and candidate.get("unit") != base.get("unit"):
        findings.append(_predicate_finding(path, "unit", base.get("unit"), candidate.get("unit")))
    return findings


def _predicate_finding(path: str, predicate: str, base_value: Any, candidate_value: Any) -> Finding:
    return Finding(
        "error",
        "refinement.field_predicate_weakened",
        f"candidate weakens inherited {predicate} predicate",
        path,
        path,
        details={"predicate": predicate, "base": base_value, "candidate": candidate_value},
    )


def _field_privacy_findings(path: str, field_name: str, base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for key in ("classification", "sensitivity"):
        if key in base:
            base_rank = _privacy_rank(base.get(key))
            candidate_rank = _privacy_rank(candidate.get(key))
            if candidate_rank < base_rank:
                findings.append(
                    Finding(
                        "error",
                        "refinement.privacy_weakened",
                        f"candidate weakens {key} for field {field_name!r}",
                        path,
                        path,
                        details={"field": field_name, "classification_key": key, "base": base.get(key), "candidate": candidate.get(key)},
                    )
                )
    if "transformation" in base and "transformation" not in candidate:
        findings.append(Finding("error", "refinement.privacy_weakened", f"candidate drops required privacy transformation for field {field_name!r}", path, path))
    return findings


def _log_policy_findings(name: str, base_spec: dict[str, Any], candidate_spec: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    base_rank = _severity_rank(_minimum_severity(base_spec))
    candidate_rank = _severity_rank(_minimum_severity(candidate_spec))
    if base_rank is not None and (candidate_rank is None or candidate_rank < base_rank):
        findings.append(
            Finding(
                "error",
                "refinement.field_predicate_weakened",
                f"candidate lowers log severity requirement for {name!r}",
                f"$.logs[name={name!r}].severity",
                f"$.logs[name={name!r}].severity",
                details={"predicate": "severity", "base": _minimum_severity(base_spec), "candidate": _minimum_severity(candidate_spec)},
            )
        )
    if base_spec.get("message_pattern") and candidate_spec.get("message_pattern") != base_spec.get("message_pattern"):
        findings.append(_predicate_finding(f"$.logs[name={name!r}].message_pattern", "message_pattern", base_spec.get("message_pattern"), candidate_spec.get("message_pattern")))
    return findings


def _scenario_and_temporal_findings(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for section, label in (
        ("scenarios", "scenario"),
        ("temporal_properties", "temporal property"),
        ("alternative_obligations", "alternative obligation"),
    ):
        base_items = _by_id(base.get(section))
        candidate_items = _by_id(candidate.get(section))
        for item_id in sorted(set(base_items) - set(candidate_items)):
            findings.append(
                Finding(
                    "error",
                    "refinement.required_signal_removed",
                    f"candidate removed inherited {label} {item_id!r}",
                    f"$.{section}[id={item_id!r}]",
                    f"$.{section}[id={item_id!r}]",
                    details={"section": section, "id": item_id},
                )
            )
    return findings


def _privacy_policy_findings(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    base_policies = base.get("privacy_classifications") if isinstance(base.get("privacy_classifications"), dict) else {}
    candidate_policies = candidate.get("privacy_classifications") if isinstance(candidate.get("privacy_classifications"), dict) else {}
    for name, base_policy in base_policies.items():
        path = f"$.privacy_classifications.{name}"
        candidate_policy = candidate_policies.get(name)
        if not isinstance(candidate_policy, dict):
            findings.append(Finding("error", "refinement.privacy_weakened", f"candidate removed privacy classification {name!r}", path, path))
            continue
        base_allowed = _as_set(base_policy.get("allowed_transformations"))
        candidate_allowed = _as_set(candidate_policy.get("allowed_transformations"))
        if base_allowed and (not candidate_allowed or not _candidate_superset(base_allowed, candidate_allowed)):
            findings.append(
                Finding(
                    "error",
                    "refinement.privacy_weakened",
                    f"candidate allows transformations outside base privacy classification {name!r}",
                    path,
                    path,
                    details={"base_allowed_transformations": sorted(base_allowed), "candidate_allowed_transformations": sorted(candidate_allowed)},
                )
            )
    return findings


def _transformation_policy_findings(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    base_policy = _transformation_policy(base)
    candidate_policy = _transformation_policy(candidate)
    base_transformations = _as_set(base_policy.get("approved_transformations"))
    candidate_transformations = _as_set(candidate_policy.get("approved_transformations"))
    if base_transformations and not _candidate_superset(base_transformations, candidate_transformations):
        findings.append(
            Finding(
                "error",
                "refinement.transformation_policy_weakened",
                "candidate approves transformations not approved by the base contract",
                "$.metadata.transformation_preservation.approved_transformations",
                "$.metadata.transformation_preservation.approved_transformations",
                details={"base": sorted(base_transformations), "candidate": sorted(candidate_transformations)},
            )
        )
    base_scenarios = _as_set(base_policy.get("preserve_scenarios"))
    candidate_scenarios = _as_set(candidate_policy.get("preserve_scenarios"))
    if base_scenarios and not _candidate_superset(candidate_scenarios, base_scenarios):
        findings.append(
            Finding(
                "error",
                "refinement.transformation_policy_weakened",
                "candidate no longer preserves every base transformation scenario",
                "$.metadata.transformation_preservation.preserve_scenarios",
                "$.metadata.transformation_preservation.preserve_scenarios",
                details={"base": sorted(base_scenarios), "candidate": sorted(candidate_scenarios)},
            )
        )
    return findings


def _strict_policy_findings(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if _strict_enabled(base, None) and not _strict_enabled(candidate, None):
        findings.append(Finding("error", "refinement.strict_policy_weakened", "candidate disables inherited strict closed-world validation", "$.metadata.strict_validation", "$.metadata.strict_validation"))
    base_strict = _strict_policy(base)
    candidate_strict = _strict_policy(candidate)
    for key in ("allow_unmodeled_services", "allow_undeclared_signals", "allowed_extra_fields", "allow_collector_transformations"):
        base_allowed = _as_set(base_strict.get(key))
        candidate_allowed = _as_set(candidate_strict.get(key))
        if candidate_allowed and not _candidate_superset(base_allowed, candidate_allowed):
            findings.append(
                Finding(
                    "error",
                    "refinement.strict_policy_weakened",
                    f"candidate adds strict-mode escape hatch values for {key}",
                    f"$.metadata.strict_validation.{key}",
                    f"$.metadata.strict_validation.{key}",
                    details={"base": sorted(base_allowed), "candidate": sorted(candidate_allowed)},
                )
            )
    return findings


def _assume_guarantee_findings(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    base_ag = base.get("assume_guarantee") if isinstance(base.get("assume_guarantee"), dict) else {}
    candidate_ag = candidate.get("assume_guarantee") if isinstance(candidate.get("assume_guarantee"), dict) else {}
    for layer in ("service_guarantees",):
        base_items = _obligation_fingerprints(base_ag.get(layer))
        candidate_items = _obligation_fingerprints(candidate_ag.get(layer))
        for missing in sorted(base_items - candidate_items):
            findings.append(Finding("error", "refinement.required_signal_removed", f"candidate removed inherited {layer} obligation", f"$.assume_guarantee.{layer}", f"$.assume_guarantee.{layer}", details={"obligation": missing}))
    for layer in ("collector_assumptions", "environment_assumptions", "oncall_obligations"):
        base_items = _obligation_fingerprints(base_ag.get(layer))
        candidate_items = _obligation_fingerprints(candidate_ag.get(layer))
        for extra in sorted(candidate_items - base_items):
            findings.append(Finding("error", "refinement.assumption_strengthened", f"candidate adds harder-to-satisfy {layer} assumption", f"$.assume_guarantee.{layer}", f"$.assume_guarantee.{layer}", details={"obligation": extra}))
    findings.extend(_sampling_and_retention_assumption_findings(base, candidate))
    return findings


def _sampling_and_retention_assumption_findings(base: dict[str, Any], candidate: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    base_sampling = _metadata(base).get("sampling") if isinstance(_metadata(base).get("sampling"), dict) else {}
    candidate_sampling = _metadata(candidate).get("sampling") if isinstance(_metadata(candidate).get("sampling"), dict) else {}
    for signal, base_policy in base_sampling.items():
        if not isinstance(base_policy, dict):
            continue
        candidate_policy = candidate_sampling.get(signal, {})
        if not isinstance(candidate_policy, dict):
            continue
        base_rate = base_policy.get("minimum_rate", base_policy.get("rate"))
        candidate_rate = candidate_policy.get("minimum_rate", candidate_policy.get("rate"))
        if isinstance(base_rate, (int, float)) and isinstance(candidate_rate, (int, float)) and candidate_rate > base_rate:
            findings.append(Finding("error", "refinement.assumption_strengthened", f"candidate requires higher {signal} sampling rate than base", f"$.metadata.sampling.{signal}.minimum_rate", f"$.metadata.sampling.{signal}.minimum_rate", details={"base": base_rate, "candidate": candidate_rate}))
    base_retention = _metadata(base).get("retention") if isinstance(_metadata(base).get("retention"), dict) else {}
    candidate_retention = _metadata(candidate).get("retention") if isinstance(_metadata(candidate).get("retention"), dict) else {}
    for key, base_days in base_retention.items():
        candidate_days = candidate_retention.get(key)
        if isinstance(base_days, (int, float)) and isinstance(candidate_days, (int, float)) and candidate_days > base_days:
            findings.append(Finding("error", "refinement.assumption_strengthened", f"candidate requires longer retention for {key} than base", f"$.metadata.retention.{key}", f"$.metadata.retention.{key}", details={"base": base_days, "candidate": candidate_days}))
    return findings


def _signals_by_key(contract: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for section in ("spans", "metrics", "logs"):
        for spec in contract.get(section, []) or []:
            if isinstance(spec, dict) and isinstance(spec.get("name"), str):
                result[(section, spec["name"])] = spec
    return result


def _required_signals(contract: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {key: spec for key, spec in _signals_by_key(contract).items() if spec.get("required", True)}


def _preserved_required_signals(base: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, str]]:
    candidate_signals = _signals_by_key(candidate)
    preserved = []
    for (section, name), spec in _required_signals(base).items():
        if (section, name) in candidate_signals and candidate_signals[(section, name)].get("required") is not False:
            preserved.append({"kind": section[:-1], "name": name})
    return preserved


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


def _type_refines(base_type: str, candidate_type: Any) -> bool:
    if candidate_type == base_type:
        return True
    return base_type == "number" and candidate_type == "integer"


def _candidate_values_subset(base_values: Any, candidate_values: Any) -> bool:
    if not isinstance(base_values, list):
        return True
    if not isinstance(candidate_values, list):
        return False
    return set(map(_stable_json, candidate_values)).issubset(set(map(_stable_json, base_values)))


def _bound_refines(bound: str, base_value: Any, candidate_value: Any) -> bool:
    if not isinstance(base_value, (int, float)) or isinstance(base_value, bool):
        return True
    if not isinstance(candidate_value, (int, float)) or isinstance(candidate_value, bool):
        return False
    return candidate_value >= base_value if bound == "min" else candidate_value <= base_value


def _candidate_superset(candidate: set[str], required: set[str]) -> bool:
    return required.issubset(candidate)


def _privacy_rank(value: Any) -> int:
    text = str(value or "").lower().replace("-", "_")
    if text in {"secret", "credential", "credentials", "token", "password", "api_key"}:
        return 4
    if text in {"pii", "personal", "sensitive"}:
        return 3
    if text in {"identifier", "tenant_identifier", "quasi_identifier"}:
        return 2
    if text in {"internal", "confidential"}:
        return 1
    return 0


def _minimum_severity(spec: dict[str, Any]) -> str | None:
    policy = spec.get("severity_policy")
    if isinstance(policy, dict) and isinstance(policy.get("min"), str):
        return policy["min"]
    if isinstance(spec.get("severity"), str):
        return spec["severity"]
    return None


def _severity_rank(value: str | None) -> int | None:
    if value is None:
        return None
    return SEVERITY_RANKS.get(value.upper())


def _by_id(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {str(item["id"]): item for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)}


def _id_comparison(base_items: Any, candidate_items: Any) -> dict[str, list[str]]:
    base_ids = set(_by_id(base_items))
    candidate_ids = set(_by_id(candidate_items))
    return {
        "preserved": sorted(base_ids & candidate_ids),
        "removed": sorted(base_ids - candidate_ids),
        "added": sorted(candidate_ids - base_ids),
    }


def _metadata(contract: dict[str, Any]) -> dict[str, Any]:
    return contract.get("metadata") if isinstance(contract.get("metadata"), dict) else {}


def _transformation_policy(contract: dict[str, Any]) -> dict[str, Any]:
    policy = _metadata(contract).get("transformation_preservation")
    return policy if isinstance(policy, dict) else {}


def _strict_policy(contract: dict[str, Any]) -> dict[str, Any]:
    policy = _metadata(contract).get("strict_validation")
    return policy if isinstance(policy, dict) else {}


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        return {str(item) for item in value}
    if isinstance(value, dict):
        return {str(key) for key, enabled in value.items() if enabled}
    return {str(value)}


def _obligation_fingerprints(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {_stable_json(item) for item in items if isinstance(item, dict)}


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
