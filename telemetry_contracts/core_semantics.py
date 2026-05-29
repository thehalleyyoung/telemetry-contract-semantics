from __future__ import annotations

from collections import Counter
from typing import Any

from .alternatives import alternative_obligation_findings, evaluate_alternative_obligations
from .findings import Finding, has_at_least
from .semantics import build_event_structure, summarize_events
from .validator import (
    _MISSING,
    _event_index,
    _field_specs,
    _lookup_field,
    _strict_enabled,
    _validate_correlation_policy,
    _validate_signal,
    _validate_strict_events,
    _validate_temporal_properties,
    _validate_temporal_sequences,
    validate_contract_shape,
    validate_events,
)

CORE_SEMANTICS_MODEL: dict[str, Any] = {
    "name": "contract-small-step-semantics-v1",
    "judgement": "⟨T,C,σ⟩ ⇓ R",
    "relation": (
        "A finite trace T and contract C evaluate by deterministic small steps: "
        "well-formedness, service projection, signal obligations, correlation, "
        "temporal sequence and temporal-logic obligations, alternative disjunctions, and optional strict closed-world "
        "checks. The denotation R is the ordered multiset of checker finding signatures; "
        "alignment holds when the small-step denotation equals validate_events(C,T)."
    ),
    "rules": [
        {"name": "WF", "meaning": "Evaluate contract shape and schema obligations before telemetry obligations."},
        {"name": "PROJECT", "meaning": "Restrict runtime satisfaction to events for C.service or unscoped events."},
        {"name": "SIGNAL", "meaning": "For each required span/log/metric, find witnesses and check field predicates."},
        {"name": "CORRELATION", "meaning": "Check configured shared correlation keys across required signal kinds."},
        {"name": "TEMPORAL", "meaning": "Check finite ordered sequences within declared incident windows."},
        {"name": "TEMPORAL-PROPERTY", "meaning": "Check safety, absence, bounded-response, ordering, and deadline properties over finite traces."},
        {"name": "ALTERNATIVE", "meaning": "Evaluate required finite disjunctions over equivalent evidence paths."},
        {"name": "STRICT", "meaning": "Optionally strengthen satisfaction with closed-world checks."},
    ],
}


def evaluate_contract_semantics(contract: dict[str, Any], events: list[dict[str, Any]], *, strict: bool | None = None) -> dict[str, Any]:
    """Evaluate a contract with an explicit small-step trace aligned to validate_events."""
    service = contract.get("service")
    relevant_events = [event for event in events if service is None or event.get("service") in {service, None}]
    steps: list[dict[str, Any]] = []
    step_findings: list[Finding] = []

    wf_findings = validate_contract_shape(contract)
    steps.append(_step("WF", "contract well-formedness", wf_findings, {"contract_service": service or "", "input_events": len(events)}))
    step_findings.extend(wf_findings)

    ignored = len(events) - len(relevant_events)
    steps.append(
        _step(
            "PROJECT",
            "service projection",
            [],
            {
                "service": service or "",
                "retained_events": len(relevant_events),
                "ignored_events": ignored,
                "counts_by_kind": summarize_events(relevant_events)["counts_by_kind"],
            },
        )
    )

    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        raw_signals = contract.get(section, []) or []
        if not isinstance(raw_signals, list):
            continue
        for signal_index, spec in enumerate(raw_signals):
            if not isinstance(spec, dict) or not isinstance(spec.get("name"), str) or not spec.get("name"):
                continue
            findings = _validate_signal(kind, section, signal_index, spec, relevant_events, contract)
            step_findings.extend(findings)
            steps.append(
                _step(
                    "SIGNAL",
                    f"{kind} {spec['name']}",
                    findings,
                    _signal_obligation(kind, section, signal_index, spec, relevant_events, contract),
                )
            )

    correlation_findings = _validate_correlation_policy(contract, relevant_events)
    step_findings.extend(correlation_findings)
    steps.append(_step("CORRELATION", "correlation policy", correlation_findings, _correlation_evidence(contract, relevant_events)))

    temporal_findings = _validate_temporal_sequences(contract, relevant_events)
    step_findings.extend(temporal_findings)
    steps.append(_step("TEMPORAL", "temporal sequences", temporal_findings, _temporal_evidence(contract)))

    temporal_property_findings = _validate_temporal_properties(contract, relevant_events)
    step_findings.extend(temporal_property_findings)
    steps.append(_step("TEMPORAL-PROPERTY", "temporal logic properties", temporal_property_findings, _temporal_property_evidence(contract)))

    alternative_report = evaluate_alternative_obligations(contract, relevant_events)
    alternative_findings = alternative_obligation_findings(contract, relevant_events)
    step_findings.extend(alternative_findings)
    steps.append(
        _step(
            "ALTERNATIVE",
            "alternative obligations",
            alternative_findings,
            {
                "summary": alternative_report["summary"],
                "obligations": [
                    {
                        "id": item["id"],
                        "required": item["required"],
                        "satisfied": item["satisfied"],
                        "winning_option": item.get("winning_option"),
                    }
                    for item in alternative_report["alternative_obligations"]
                ],
            },
        )
    )

    if _strict_enabled(contract, strict):
        strict_findings = _validate_strict_events(contract, events)
        step_findings.extend(strict_findings)
        steps.append(_step("STRICT", "closed-world validation", strict_findings, _strict_evidence(events)))
    else:
        steps.append(_step("STRICT", "closed-world validation disabled", [], {"enabled": False}))

    checker_findings = validate_events(contract, events, strict=strict)
    step_signatures = _finding_signatures(step_findings)
    checker_signatures = _finding_signatures(checker_findings)
    aligned = step_signatures == checker_signatures
    summary = {
        "pass": not has_at_least(checker_findings, "error"),
        "aligned_with_checker": aligned,
        "events": len(events),
        "relevant_events": len(relevant_events),
        "steps": len(steps),
        "findings": len(checker_findings),
        "findings_by_severity": dict(sorted(Counter(item.severity for item in checker_findings).items())),
        "findings_by_code": dict(sorted(Counter(item.code for item in checker_findings).items())),
    }
    return {
        "model": CORE_SEMANTICS_MODEL,
        "service": service or "",
        "summary": summary,
        "small_steps": steps,
        "denotation": {
            "finding_signatures": step_signatures,
            "checker_finding_signatures": checker_signatures,
            "mismatches": _signature_mismatches(step_signatures, checker_signatures),
        },
        "findings": [finding.to_dict() for finding in checker_findings],
        "event_structure": build_event_structure(relevant_events),
    }


def format_core_semantics_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Contract semantic evaluation: {report.get('service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Judgement: `{report['model']['judgement']}`",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Aligned with deterministic checker: `{str(summary['aligned_with_checker']).lower()}`",
        f"- Events: {summary['events']} input / {summary['relevant_events']} service-relevant",
        f"- Small steps: {summary['steps']}",
        f"- Findings: {summary['findings']}",
        f"- Findings by code: `{summary['findings_by_code']}`",
        "",
        "## Relation",
        "",
        report["model"]["relation"],
        "",
        "## Rules",
        "",
    ]
    for rule in report["model"]["rules"]:
        lines.append(f"- **{rule['name']}** — {rule['meaning']}")
    lines.extend(["", "## Small-step derivation", ""])
    for index, step in enumerate(report["small_steps"], start=1):
        lines.extend(
            [
                f"### {index}. {step['rule']} — {step['label']}",
                "",
                f"- Status: `{step['status']}`",
                f"- Findings: {step['finding_count']}",
            ]
        )
        evidence = step.get("evidence") or {}
        if step["rule"] == "SIGNAL":
            lines.append(f"- Obligation: `{evidence.get('kind')} {evidence.get('name')}` required=`{str(evidence.get('required')).lower()}`")
            lines.append(f"- Matching event lines: `{evidence.get('matching_event_lines', [])}`")
            field_summaries = evidence.get("fields", [])
            if field_summaries:
                field_text = ", ".join(f"{item['name']}={item['status']}" for item in field_summaries)
                lines.append(f"- Fields: {field_text}")
        elif evidence:
            lines.append(f"- Evidence: `{_short_jsonish(evidence)}`")
        if step.get("findings"):
            lines.append("- Step findings:")
            for finding in step["findings"]:
                lines.append(f"  - `{finding['code']}` {finding['message']}")
        lines.append("")
    lines.extend(["## Denotation alignment", ""])
    denotation = report["denotation"]
    lines.append(f"- Small-step finding signatures: {len(denotation['finding_signatures'])}")
    lines.append(f"- Checker finding signatures: {len(denotation['checker_finding_signatures'])}")
    lines.append(f"- Mismatches: `{denotation['mismatches']}`")
    if report.get("findings"):
        lines.extend(["", "## Findings", ""])
        for finding in report["findings"]:
            lines.append(f"- **{finding['severity']} `{finding['code']}`** ({finding.get('formal_clause', 'unclassified')}): {finding['message']}")
    return "\n".join(lines).rstrip()


def _step(rule: str, label: str, findings: list[Finding], evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule": rule,
        "label": label,
        "status": "violated" if has_at_least(findings, "error") else "satisfied",
        "finding_count": len(findings),
        "findings": [finding.to_dict() for finding in findings],
        "evidence": evidence,
    }


def _signal_obligation(kind: str, section: str, signal_index: int, spec: dict[str, Any], events: list[dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any]:
    name = spec.get("name")
    matches = [event for event in events if event.get("kind") == kind and event.get("name") == name]
    field_summaries = []
    field_specs = _field_specs(spec, contract)
    if kind == "metric" and isinstance(spec.get("value"), dict):
        field_specs = {"value": spec["value"], **field_specs}
    for field_name in sorted(field_specs):
        present_lines = []
        missing_lines = []
        for event in matches:
            value, _ = _lookup_field(event, field_name)
            if value is _MISSING:
                missing_lines.append(_event_index(event))
            else:
                present_lines.append(_event_index(event))
        required = field_specs[field_name].get("required", True) and field_specs[field_name].get("transformation") != "omitted"
        if present_lines and (not required or not missing_lines):
            status = "present"
        elif present_lines:
            status = "partial"
        elif required:
            status = "absent"
        else:
            status = "optional-absent"
        field_summaries.append(
            {
                "name": field_name,
                "required": required,
                "status": status,
                "present_event_lines": present_lines,
                "missing_event_lines": missing_lines,
            }
        )
    return {
        "contract_path": f"$.{section}[{signal_index}]",
        "kind": kind,
        "name": name,
        "required": spec.get("required", True) is not False,
        "matching_event_lines": [_event_index(event) for event in matches],
        "fields": field_summaries,
    }


def _correlation_evidence(contract: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    policy = contract.get("correlation")
    if not isinstance(policy, dict):
        return {"declared": False}
    keys = [key for key in policy.get("keys", []) if isinstance(key, str)]
    require_on = policy.get("require_on", ["spans", "logs"])
    return {"declared": True, "keys": keys, "require_on": require_on, "event_count": len(events)}


def _temporal_evidence(contract: dict[str, Any]) -> dict[str, Any]:
    sequences = contract.get("temporal_sequences") or []
    if not isinstance(sequences, list):
        return {"sequence_count": 0}
    return {
        "sequence_count": len(sequences),
        "sequences": [
            {"id": sequence.get("id", index), "steps": len(sequence.get("steps", []) or []), "window_ms": sequence.get("window_ms")}
            for index, sequence in enumerate(sequences)
            if isinstance(sequence, dict)
        ],
    }


def _temporal_property_evidence(contract: dict[str, Any]) -> dict[str, Any]:
    properties = contract.get("temporal_properties") or []
    if not isinstance(properties, list):
        return {"property_count": 0}
    return {
        "property_count": len(properties),
        "properties": [
            {
                "id": prop.get("id", index),
                "type": prop.get("type"),
                "group_by": prop.get("group_by", []),
                "within_ms": prop.get("within_ms"),
            }
            for index, prop in enumerate(properties)
            if isinstance(prop, dict)
        ],
    }


def _strict_evidence(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {"enabled": True, "events_checked": len(events)}


def _finding_signatures(findings: list[Finding]) -> list[dict[str, Any]]:
    return [
        {
            "severity": finding.severity,
            "code": finding.code,
            "path": finding.path,
            "contract_path": finding.contract_path or "",
            "event_index": finding.event_index,
            "message": finding.message,
        }
        for finding in findings
    ]


def _signature_mismatches(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    left_counts = Counter(_signature_key(item) for item in left)
    right_counts = Counter(_signature_key(item) for item in right)
    missing = list((right_counts - left_counts).elements())
    extra = list((left_counts - right_counts).elements())
    return {"missing_from_small_step": missing, "extra_in_small_step": extra}


def _signature_key(item: dict[str, Any]) -> tuple[Any, ...]:
    return (item.get("severity"), item.get("code"), item.get("path"), item.get("contract_path"), item.get("event_index"), item.get("message"))


def _short_jsonish(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 500 else text[:497] + "..."
