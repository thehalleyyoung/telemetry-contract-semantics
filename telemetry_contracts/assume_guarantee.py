from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .alternatives import evaluate_alternative_requirement
from .findings import Finding, has_at_least
from .scenario import choose_scenario, evaluate_scenario_adequacy
from .validator import (
    _MISSING,
    _event_index,
    _event_transformations,
    _lookup_field,
    _validate_temporal_properties,
)

ASSUME_GUARANTEE_MODEL: dict[str, Any] = {
    "name": "assume-guarantee-telemetry-contracts-v1",
    "judgement": "A,T ⊢ layer obligation ⇓ satisfied | violated",
    "relation": (
        "An assume-guarantee telemetry contract partitions finite-trace obligations by accountable layer: "
        "service emission guarantees, collector/exporter assumptions, environment assumptions, and on-call "
        "diagnostic obligations. A layer obligation is satisfied when its declared signal, scenario, temporal, "
        "alternative, or collector-transformation evidence is witnessed in the supplied finite trace; otherwise "
        "the report emits a layer-specific counterexample with event indices and missing fields."
    ),
    "layers": ["service", "collector", "environment", "oncall"],
}

SECTION_LAYERS = {
    "service_guarantees": ("service", "service emission guarantee"),
    "collector_assumptions": ("collector", "collector/exporter assumption"),
    "environment_assumptions": ("environment", "environment assumption"),
    "oncall_obligations": ("oncall", "on-call diagnostic obligation"),
}


def validate_assume_guarantee_shape(contract: dict[str, Any]) -> list[Finding]:
    raw = contract.get("assume_guarantee")
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return [Finding("error", "contract.assume_guarantee", "assume_guarantee must be an object", "$.assume_guarantee")]
    findings: list[Finding] = []
    for section in raw:
        if section not in SECTION_LAYERS:
            findings.append(Finding("error", "contract.assume_guarantee", f"unknown assume-guarantee section {section!r}", f"$.assume_guarantee.{section}"))
    for section in SECTION_LAYERS:
        obligations = raw.get(section, [])
        if obligations is None:
            continue
        if not isinstance(obligations, list):
            findings.append(Finding("error", "contract.assume_guarantee", f"{section} must be an array", f"$.assume_guarantee.{section}"))
            continue
        for index, obligation in enumerate(obligations):
            path = f"$.assume_guarantee.{section}[{index}]"
            if not isinstance(obligation, dict):
                findings.append(Finding("error", "contract.assume_guarantee", "assume-guarantee obligation must be an object", path))
                continue
            if not isinstance(obligation.get("id"), str) or not obligation.get("id"):
                findings.append(Finding("error", "contract.assume_guarantee", "assume-guarantee obligation must declare a non-empty id", f"{path}.id"))
            if "required" in obligation and not isinstance(obligation["required"], bool):
                findings.append(Finding("error", "contract.assume_guarantee", "assume-guarantee required flag must be boolean", f"{path}.required"))
            if "fields" in obligation and (not isinstance(obligation["fields"], list) or not all(isinstance(field, str) and field for field in obligation["fields"])):
                findings.append(Finding("error", "contract.assume_guarantee", "assume-guarantee fields must be an array of strings", f"{path}.fields"))
            if "any_of" in obligation and (not isinstance(obligation["any_of"], list) or not obligation["any_of"]):
                findings.append(Finding("error", "contract.assume_guarantee", "assume-guarantee any_of must be a non-empty array", f"{path}.any_of"))
            has_known_evidence = any(key in obligation for key in ("signal", "kind", "scenario", "temporal_property", "no_undocumented_transformations", "any_of"))
            if not has_known_evidence:
                findings.append(Finding("error", "contract.assume_guarantee", "assume-guarantee obligation must declare signal/kind, scenario, temporal_property, any_of, or no_undocumented_transformations", path))
    return findings


def evaluate_assume_guarantee(contract: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    shape_findings = validate_assume_guarantee_shape(contract)
    obligations: list[dict[str, Any]] = []
    findings: list[Finding] = list(shape_findings)
    raw = contract.get("assume_guarantee") if isinstance(contract.get("assume_guarantee"), dict) else {}
    for section, (layer, label) in SECTION_LAYERS.items():
        raw_obligations = raw.get(section, []) if isinstance(raw, dict) else []
        if not isinstance(raw_obligations, list):
            continue
        for index, obligation in enumerate(raw_obligations):
            if not isinstance(obligation, dict):
                continue
            path = f"$.assume_guarantee.{section}[{index}]"
            result = _evaluate_obligation(contract, events, obligation, path, layer, label)
            obligations.append(result)
            findings.extend(Finding(item["severity"], item["code"], item["message"], item["path"], item.get("contract_path"), item.get("event_index"), item.get("details")) for item in result.get("findings", []))
    status_counts = Counter(item["status"] for item in obligations)
    layer_counts = {layer: dict(Counter(item["status"] for item in obligations if item["layer"] == layer)) for layer, _ in SECTION_LAYERS.values()}
    finding_dicts = [finding.to_dict() for finding in findings]
    return {
        "model": ASSUME_GUARANTEE_MODEL,
        "service": contract.get("service", ""),
        "summary": {
            "pass": not has_at_least(findings, "error"),
            "obligations": len(obligations),
            "satisfied": status_counts.get("satisfied", 0),
            "violated": status_counts.get("violated", 0),
            "not_applicable": status_counts.get("not-applicable", 0),
            "findings": len(finding_dicts),
            "findings_by_code": dict(sorted(Counter(item["code"] for item in finding_dicts).items())),
            "by_layer": layer_counts,
        },
        "obligations": obligations,
        "findings": finding_dicts,
        "limitations": [
            "The report checks finite supplied artifacts; it does not prove obligations over all production executions.",
            "Collector-preservation assumptions that require before/after traces should be paired with the preservation command for transformation-local proof evidence.",
        ],
    }


def format_assume_guarantee_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Assume-guarantee report: {report.get('service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Judgement: `{report['model']['judgement']}`",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Obligations: {summary['obligations']}",
        f"- Satisfied: {summary['satisfied']}",
        f"- Violated: {summary['violated']}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        "",
        "## Relation",
        "",
        report["model"]["relation"],
        "",
        "## Layer summary",
        "",
        "| Layer | Satisfied | Violated | Not applicable |",
        "| --- | ---: | ---: | ---: |",
    ]
    for layer in report["model"]["layers"]:
        counts = summary["by_layer"].get(layer, {})
        lines.append(f"| {layer} | {counts.get('satisfied', 0)} | {counts.get('violated', 0)} | {counts.get('not-applicable', 0)} |")
    lines.extend(["", "## Obligations", ""])
    for item in report["obligations"]:
        lines.append(f"- **{item['id']}** `{item['status']}` — {item['layer_label']}")
        if item.get("description"):
            lines.append(f"  - Description: {item['description']}")
        lines.append(f"  - Evidence: `{_short_json(item.get('evidence', {}))}`")
        if item.get("findings"):
            lines.append("  - Findings:")
            for finding in item["findings"]:
                lines.append(f"    - `{finding['code']}` {finding['message']}")
    if report.get("limitations"):
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines).rstrip()


def _evaluate_obligation(contract: dict[str, Any], events: list[dict[str, Any]], obligation: dict[str, Any], path: str, layer: str, label: str) -> dict[str, Any]:
    required = obligation.get("required", True) is not False
    severity = "error" if required else "warning"
    obligation_id = str(obligation.get("id", f"{layer}-obligation"))
    base = {
        "id": obligation_id,
        "layer": layer,
        "layer_label": label,
        "required": required,
        "description": obligation.get("description", obligation.get("purpose", "")),
        "contract_path": path,
    }
    if "any_of" in obligation:
        alt = evaluate_alternative_requirement(obligation, events, path)
        findings = []
        if not alt["satisfied"] and required:
            findings.append(_finding_dict(severity, "ag.alternative_missing", f"{label} '{obligation_id}' requires one satisfied alternative evidence path", alt.get("evidence_path", "events[alternative]"), path, None, {"layer": layer, "obligation_id": obligation_id, "options": alt.get("options", [])}))
        return {**base, "status": "satisfied" if alt["satisfied"] else "violated", "evidence": alt, "findings": findings}
    if obligation.get("no_undocumented_transformations") is True:
        return _evaluate_transformations(contract, events, obligation, base, path, severity)
    if "scenario" in obligation:
        scenario = choose_scenario(contract, scenario_id=str(obligation.get("scenario")))
        report = evaluate_scenario_adequacy(contract, events, scenario)
        findings = []
        if not report["answerable"] and required:
            findings.append(_finding_dict(severity, "ag.scenario_unanswerable", f"{label} '{obligation_id}' requires scenario '{obligation.get('scenario')}' to be answerable", f"scenario[{obligation.get('scenario')}]", path, None, {"layer": layer, "obligation_id": obligation_id, "scenario": obligation.get("scenario"), "missing_evidence": report.get("missing_evidence", [])}))
        return {**base, "status": "satisfied" if report["answerable"] else "violated", "evidence": {"scenario": report.get("id"), "answerable": report["answerable"], "missing_evidence": report.get("missing_evidence", [])}, "findings": findings}
    if "temporal_property" in obligation:
        temporal_id = str(obligation.get("temporal_property"))
        temporal_findings = [finding for finding in _validate_temporal_properties(contract, events) if finding.details and finding.details.get("property") == temporal_id]
        findings = []
        if temporal_findings and required:
            findings.append(_finding_dict(severity, "ag.temporal_property", f"{label} '{obligation_id}' requires temporal property '{temporal_id}' to hold", temporal_findings[0].path, path, temporal_findings[0].event_index, {"layer": layer, "obligation_id": obligation_id, "property_id": temporal_id, "violations": [item.to_dict() for item in temporal_findings]}))
        return {**base, "status": "violated" if temporal_findings else "satisfied", "evidence": {"temporal_property": temporal_id, "violations": [item.to_dict() for item in temporal_findings]}, "findings": findings}
    return _evaluate_signal_obligation(events, obligation, base, path, severity)


def _evaluate_signal_obligation(events: list[dict[str, Any]], obligation: dict[str, Any], base: dict[str, Any], path: str, severity: str) -> dict[str, Any]:
    kind = _normalize_kind(obligation.get("signal", obligation.get("kind")))
    name = obligation.get("name")
    fields = [str(field) for field in obligation.get("fields", []) or []]
    matches = [(index, event) for index, event in enumerate(events) if event.get("kind") == kind and event.get("name") == name]
    observed_fields = sorted({field for _, event in matches for field in fields if _lookup_field(event, field)[0] is not _MISSING})
    missing_fields = [field for field in fields if not any(_lookup_field(event, field)[0] is not _MISSING for _, event in matches)]
    predicate_field = obligation.get("field")
    predicate_ok = True
    predicate_witnesses: list[int] = []
    if isinstance(predicate_field, str):
        predicate_ok = False
        for _, event in matches:
            value, _ = _lookup_field(event, predicate_field)
            if value is _MISSING:
                continue
            if "equals" in obligation and value != obligation["equals"]:
                continue
            if "present" in obligation and bool(obligation["present"]) is False:
                continue
            predicate_ok = True
            predicate_witnesses.append(_event_index(event))
    finding_dicts = []
    obligation_id = base["id"]
    layer = base["layer"]
    if not matches and base["required"]:
        finding_dicts.append(_finding_dict(severity, "ag.missing_signal", f"{base['layer_label']} '{obligation_id}' requires {kind} '{name}'", f"events[{kind}={name}]", path, None, {"layer": layer, "obligation_id": obligation_id, "signal": kind, "name": name}))
    for field in missing_fields:
        if base["required"]:
            finding_dicts.append(_finding_dict(severity, "ag.missing_field", f"{base['layer_label']} '{obligation_id}' requires field '{field}' on {kind} '{name}'", f"events[{kind}={name}].{field}", f"{path}.fields", None, {"layer": layer, "obligation_id": obligation_id, "matching_event_indices": [index for index, _ in matches]}))
    if not predicate_ok and base["required"]:
        finding_dicts.append(_finding_dict(severity, "ag.predicate", f"{base['layer_label']} '{obligation_id}' predicate on field '{predicate_field}' was not witnessed", f"events[{kind}={name}].{predicate_field}", path, None, {"layer": layer, "obligation_id": obligation_id, "expected": obligation.get("equals")}))
    status = "satisfied" if matches and not missing_fields and predicate_ok else "violated"
    return {**base, "status": status, "evidence": {"signal": kind, "name": name, "matching_event_indices": [_event_index(event) for _, event in matches], "fields": fields, "observed_fields": observed_fields, "missing_fields": missing_fields, "predicate_witnesses": predicate_witnesses}, "findings": finding_dicts}


def _evaluate_transformations(contract: dict[str, Any], events: list[dict[str, Any]], obligation: dict[str, Any], base: dict[str, Any], path: str, severity: str) -> dict[str, Any]:
    metadata = contract.get("metadata")
    preservation = metadata.get("transformation_preservation") if isinstance(metadata, dict) else None
    approved = set(str(item) for item in obligation.get("approved_transformations", []) if isinstance(item, str))
    if isinstance(preservation, dict):
        approved.update(str(item) for item in preservation.get("approved_transformations", []) if isinstance(item, str))
    observed: dict[str, list[int]] = {}
    for event in events:
        for transformation in _event_transformations(event):
            observed.setdefault(transformation, []).append(_event_index(event))
    undocumented = {name: indices for name, indices in observed.items() if name not in approved}
    findings = []
    if undocumented and base["required"]:
        findings.append(_finding_dict(severity, "ag.undocumented_transformation", f"{base['layer_label']} '{base['id']}' observed undocumented collector transformations", "events[*].transformations", path, None, {"layer": base["layer"], "obligation_id": base["id"], "undocumented_transformations": undocumented, "approved_transformations": sorted(approved)}))
    return {**base, "status": "violated" if undocumented else "satisfied", "evidence": {"approved_transformations": sorted(approved), "observed_transformations": observed, "undocumented_transformations": undocumented}, "findings": findings}


def _finding_dict(severity: str, code: str, message: str, path: str, contract_path: str, event_index: int | None, details: dict[str, Any]) -> dict[str, Any]:
    return Finding(severity, code, message, path, contract_path, event_index, details).to_dict()


def _normalize_kind(value: Any) -> str:
    text = str(value or "").lower()
    return {"spans": "span", "logs": "log", "metrics": "metric"}.get(text, text)


def _short_json(value: Any) -> str:
    text = json.dumps(value, sort_keys=True)
    return text if len(text) <= 240 else text[:237] + "..."
