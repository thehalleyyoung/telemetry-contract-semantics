from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .findings import Finding

SignalKind = str


def validate_contract_shape(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if contract.get("version") not in {"1", "1.0", 1}:
        findings.append(Finding("warning", "contract.version", "contract version should be 1", "$.version"))
    if not isinstance(contract.get("service"), str) or not contract.get("service"):
        findings.append(Finding("error", "contract.service", "contract must declare a non-empty service", "$.service"))
    for section in ("spans", "metrics", "logs"):
        if section in contract and not isinstance(contract[section], list):
            findings.append(Finding("error", "contract.section_type", f"{section} must be a list", f"$.{section}"))
    return findings


def validate_events(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    findings = validate_contract_shape(contract)
    service = contract.get("service")
    relevant_events = [event for event in events if service is None or event.get("service") in {service, None}]
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for signal_index, spec in enumerate(contract.get(section, []) or []):
            if not isinstance(spec, dict):
                findings.append(Finding("error", "contract.signal_type", f"{section}[{signal_index}] must be an object", f"$.{section}[{signal_index}]"))
                continue
            findings.extend(_validate_signal(kind, section, signal_index, spec, relevant_events))
    return findings


def _validate_signal(kind: str, section: str, signal_index: int, spec: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    name = spec.get("name")
    path = f"$.{section}[{signal_index}]"
    if not isinstance(name, str) or not name:
        return [Finding("error", "contract.signal_name", "signal must declare a non-empty name", f"{path}.name")]
    matches = [event for event in events if event.get("kind") == kind and event.get("name") == name]
    if spec.get("required", True) and not matches:
        findings.append(Finding("error", "telemetry.missing_signal", f"required {kind} '{name}' was not emitted", f"events[{kind}={name}]", path))
        return findings
    if kind == "log":
        findings.extend(_validate_log_patterns(spec, matches, path))
    if kind == "metric" and isinstance(spec.get("value"), dict):
        for event in matches:
            findings.extend(_validate_field("value", spec["value"], event.get("value"), event, f"{path}.value"))
    field_specs = _field_specs(spec)
    for event in matches:
        for field_name, field_spec in field_specs.items():
            value, value_path = _lookup_field(event, field_name)
            if value is _MISSING:
                if field_spec.get("required", True):
                    findings.append(Finding("error", "telemetry.missing_field", f"{kind} '{name}' missing required field '{field_name}'", value_path, f"{path}.fields.{field_name}", _event_index(event)))
                continue
            findings.extend(_validate_field(field_name, field_spec, value, event, f"{path}.fields.{field_name}"))
    findings.extend(_validate_cardinality(kind, name, field_specs, matches, path))
    return findings


def _field_specs(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for container in ("fields", "attributes", "tags"):
        raw = spec.get(container, {}) or {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, dict):
                    merged[key] = value
                else:
                    merged[key] = {"type": str(value)}
    return merged


_MISSING = object()


def _lookup_field(event: dict[str, Any], field_name: str) -> tuple[Any, str]:
    for container in ("attributes", "tags", "fields"):
        values = event.get(container)
        if isinstance(values, dict) and field_name in values:
            return values[field_name], f"event[{_event_index(event)}].{container}.{field_name}"
    if field_name in event:
        return event[field_name], f"event[{_event_index(event)}].{field_name}"
    return _MISSING, f"event[{_event_index(event)}].{field_name}"


def _event_index(event: dict[str, Any]) -> int | None:
    line = event.get("_line")
    return line if isinstance(line, int) else None


def _validate_field(field_name: str, spec: dict[str, Any], value: Any, event: dict[str, Any], contract_path: str) -> list[Finding]:
    findings: list[Finding] = []
    event_path = f"event[{_event_index(event)}].{field_name}"
    expected_type = spec.get("type")
    if expected_type and not _matches_type(value, str(expected_type)):
        findings.append(Finding("error", "telemetry.field_type", f"field '{field_name}' expected {expected_type}, got {type(value).__name__}", event_path, contract_path, _event_index(event), {"value": value}))
        return findings
    allowed = spec.get("allowed_values")
    if allowed is not None and value not in allowed:
        findings.append(Finding("error", "telemetry.allowed_values", f"field '{field_name}' value {value!r} is not allowed", event_path, contract_path, _event_index(event), {"allowed_values": allowed}))
    pattern = spec.get("pattern") or spec.get("regex")
    if pattern is not None:
        if not isinstance(value, str):
            findings.append(Finding("error", "telemetry.pattern_type", f"field '{field_name}' must be a string to match pattern", event_path, contract_path, _event_index(event)))
        else:
            try:
                if re.fullmatch(str(pattern), value) is None:
                    findings.append(Finding("error", "telemetry.pattern", f"field '{field_name}' value {value!r} does not match {pattern!r}", event_path, contract_path, _event_index(event)))
            except re.error as exc:
                findings.append(Finding("error", "contract.invalid_regex", f"invalid regex for field '{field_name}': {exc}", contract_path))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "min" in spec and value < spec["min"]:
            findings.append(Finding("error", "telemetry.numeric_min", f"field '{field_name}' value {value} is below minimum {spec['min']}", event_path, contract_path, _event_index(event)))
        if "max" in spec and value > spec["max"]:
            findings.append(Finding("error", "telemetry.numeric_max", f"field '{field_name}' value {value} is above maximum {spec['max']}", event_path, contract_path, _event_index(event)))
    return findings


def _matches_type(value: Any, expected: str) -> bool:
    aliases = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "dict": "object", "list": "array"}
    expected = aliases.get(expected, expected)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    return False


def _validate_cardinality(kind: str, name: str, field_specs: dict[str, dict[str, Any]], matches: list[dict[str, Any]], path: str) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, set[Any]] = defaultdict(set)
    for event in matches:
        for field_name, field_spec in field_specs.items():
            value, _ = _lookup_field(event, field_name)
            if value is not _MISSING and isinstance(value, (str, int, float, bool)):
                seen[field_name].add(value)
    for field_name, values in seen.items():
        max_count = ((field_specs[field_name].get("cardinality") or {}).get("max"))
        if max_count is not None and len(values) > max_count:
            findings.append(Finding("warning", "telemetry.cardinality", f"{kind} '{name}' field '{field_name}' has cardinality {len(values)} over hint {max_count}", f"events[{kind}={name}].{field_name}", f"{path}.fields.{field_name}.cardinality", None, {"distinct_values": len(values)}))
    return findings


def _validate_log_patterns(spec: dict[str, Any], matches: list[dict[str, Any]], path: str) -> list[Finding]:
    findings: list[Finding] = []
    pattern = spec.get("message_pattern")
    severity = spec.get("severity")
    for event in matches:
        message = event.get("message", "")
        if pattern is not None:
            try:
                if not isinstance(message, str) or re.search(str(pattern), message) is None:
                    findings.append(Finding("error", "telemetry.log_message", f"log '{spec.get('name')}' message does not match {pattern!r}", f"event[{_event_index(event)}].message", f"{path}.message_pattern", _event_index(event)))
            except re.error as exc:
                findings.append(Finding("error", "contract.invalid_regex", f"invalid log message regex: {exc}", f"{path}.message_pattern"))
        if severity is not None and event.get("severity") != severity:
            findings.append(Finding("error", "telemetry.log_severity", f"log '{spec.get('name')}' severity must be {severity}", f"event[{_event_index(event)}].severity", f"{path}.severity", _event_index(event)))
    return findings
