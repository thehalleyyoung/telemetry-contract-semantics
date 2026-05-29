from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .findings import Finding

SignalKind = str
PRIMITIVE_TYPES = {"string", "integer", "number", "boolean", "object", "array", "null"}

BUILTIN_FORBIDDEN_PATTERNS: dict[str, str] = {
    "email": r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    "bearer_token": r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}",
    "jwt": r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b",
    "password_assignment": r"(?i)(password|passwd|pwd)\s*[:=]\s*[^,\s]+",
    "credit_card": r"\b(?:\d[ -]*?){13,19}\b",
}

SENSITIVE_FIELD_NAMES = re.compile(r"(?i)(email|password|passwd|pwd|token|secret|authorization|cookie|api[_-]?key|session[_-]?id|ssn|credit[_-]?card)")
RAW_SECRET_VALUE = re.compile(
    r"(?i)(\bbearer\s+[A-Za-z0-9._~+/=-]{8,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})"
)


def validate_contract_shape(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if contract.get("version") not in {"1", "1.0", 1}:
        findings.append(Finding("warning", "contract.version", "contract version should be 1", "$.version"))
    if not isinstance(contract.get("service"), str) or not contract.get("service"):
        findings.append(Finding("error", "contract.service", "contract must declare a non-empty service", "$.service"))
    for section in ("spans", "metrics", "logs"):
        if section in contract and not isinstance(contract[section], list):
            findings.append(Finding("error", "contract.section_type", f"{section} must be a list", f"$.{section}"))
            continue
        raw_signals = contract.get(section, []) or []
        if not isinstance(raw_signals, list):
            continue
        for signal_index, spec in enumerate(raw_signals):
            signal_path = f"$.{section}[{signal_index}]"
            if not isinstance(spec, dict):
                findings.append(Finding("error", "contract.signal_type", f"{section}[{signal_index}] must be an object", signal_path))
                continue
            if not isinstance(spec.get("name"), str) or not spec.get("name"):
                findings.append(Finding("error", "contract.signal_name", "signal must declare a non-empty name", f"{signal_path}.name"))
            if "required" in spec and not isinstance(spec["required"], bool):
                findings.append(Finding("error", "contract.required_type", "signal required flag must be a boolean", f"{signal_path}.required"))
            if section == "metrics" and isinstance(spec.get("value"), dict):
                findings.extend(_validate_field_spec("value", spec["value"], f"{signal_path}.value"))
            if section == "logs" and spec.get("message_pattern") is not None:
                findings.extend(_validate_regex(str(spec["message_pattern"]), f"{signal_path}.message_pattern", "invalid log message regex"))
            for container in ("fields", "attributes", "tags"):
                raw_fields = spec.get(container, {}) or {}
                if not isinstance(raw_fields, dict):
                    findings.append(Finding("error", "contract.section_type", f"{container} must be an object", f"{signal_path}.{container}"))
                    continue
                for field_name, field_spec in raw_fields.items():
                    normalized_spec = field_spec if isinstance(field_spec, dict) else {"type": str(field_spec)}
                    field_path = f"{signal_path}.{container}.{field_name}"
                    findings.extend(_validate_field_spec(str(field_name), normalized_spec, field_path))
                    if SENSITIVE_FIELD_NAMES.search(str(field_name)) and not _declares_sensitivity(normalized_spec):
                        findings.append(
                            Finding(
                                "warning",
                                "contract.sensitive_field_unclassified",
                                f"field '{field_name}' appears sensitive but has no sensitivity classification",
                                field_path,
                            )
                        )
    return findings


def validate_events(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    findings = validate_contract_shape(contract)
    service = contract.get("service")
    relevant_events = [event for event in events if service is None or event.get("service") in {service, None}]
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for signal_index, spec in enumerate(contract.get(section, []) or []):
            if not isinstance(spec, dict):
                continue
            if not isinstance(spec.get("name"), str) or not spec.get("name"):
                continue
            findings.extend(_validate_signal(kind, section, signal_index, spec, relevant_events))
    return findings


def _validate_field_spec(field_name: str, spec: dict[str, Any], path: str) -> list[Finding]:
    findings: list[Finding] = []
    expected_type = spec.get("type")
    if expected_type is not None:
        normalized = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "dict": "object", "list": "array"}.get(str(expected_type), str(expected_type))
        if normalized not in PRIMITIVE_TYPES:
            findings.append(Finding("error", "contract.field_type", f"field '{field_name}' has unknown type {expected_type!r}", f"{path}.type"))
    if "required" in spec and not isinstance(spec["required"], bool):
        findings.append(Finding("error", "contract.required_type", f"field '{field_name}' required flag must be a boolean", f"{path}.required"))
    if "allowed_values" in spec and not isinstance(spec["allowed_values"], list):
        findings.append(Finding("error", "contract.allowed_values_type", f"field '{field_name}' allowed_values must be an array", f"{path}.allowed_values"))
    for regex_key in ("pattern", "regex"):
        if regex_key in spec:
            findings.extend(_validate_regex(str(spec[regex_key]), f"{path}.{regex_key}", f"invalid regex for field '{field_name}'"))
    findings.extend(_validate_forbidden_pattern_specs(field_name, spec, path))
    for bound in ("min", "max"):
        if bound in spec and (not isinstance(spec[bound], (int, float)) or isinstance(spec[bound], bool)):
            findings.append(Finding("error", "contract.numeric_bound_type", f"field '{field_name}' {bound} must be numeric", f"{path}.{bound}"))
    if all(bound in spec and isinstance(spec[bound], (int, float)) and not isinstance(spec[bound], bool) for bound in ("min", "max")) and spec["min"] > spec["max"]:
        findings.append(Finding("error", "contract.numeric_bounds", f"field '{field_name}' min must be <= max", path))
    return findings


def _validate_regex(pattern: str, path: str, message: str) -> list[Finding]:
    try:
        re.compile(pattern)
    except re.error as exc:
        return [Finding("error", "contract.invalid_regex", f"{message}: {exc}", path)]
    return []


def _validate_forbidden_pattern_specs(field_name: str, spec: dict[str, Any], path: str) -> list[Finding]:
    if "forbidden_patterns" not in spec:
        return []
    patterns = spec.get("forbidden_patterns") or []
    if isinstance(patterns, (str, dict)):
        patterns = [patterns]
    if not isinstance(patterns, list):
        return [Finding("error", "contract.forbidden_patterns_type", f"field '{field_name}' forbidden_patterns must be a string, object, or array", f"{path}.forbidden_patterns")]
    findings: list[Finding] = []
    for index, pattern_spec in enumerate(patterns):
        pattern_path = f"{path}.forbidden_patterns[{index}]"
        if isinstance(pattern_spec, str):
            if pattern_spec not in BUILTIN_FORBIDDEN_PATTERNS:
                findings.extend(_validate_regex(pattern_spec, pattern_path, f"invalid forbidden regex for field '{field_name}'"))
        elif isinstance(pattern_spec, dict):
            pattern = pattern_spec.get("pattern", pattern_spec.get("regex"))
            if not isinstance(pattern, str):
                findings.append(Finding("error", "contract.forbidden_patterns_type", f"field '{field_name}' forbidden pattern object must include pattern or regex", pattern_path))
            else:
                findings.extend(_validate_regex(pattern, pattern_path, f"invalid forbidden regex for field '{field_name}'"))
        else:
            findings.append(Finding("error", "contract.forbidden_patterns_type", f"field '{field_name}' forbidden pattern entry must be a string or object", pattern_path))
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
    findings.extend(_validate_forbidden_patterns(field_name, spec, value, event, contract_path, event_path))
    findings.extend(_validate_sensitive_value(field_name, spec, value, event, contract_path, event_path))
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
    for field_name, field_spec in field_specs.items():
        cardinality = field_spec.get("cardinality") or {}
        if isinstance(cardinality, dict) and cardinality.get("policy") in {"bounded", "forbid_unbounded", "budget"} and cardinality.get("max") is None:
            findings.append(
                Finding(
                    "warning",
                    "telemetry.cardinality_policy",
                    f"{kind} '{name}' field '{field_name}' declares a bounded cardinality policy without a max",
                    f"events[{kind}={name}].{field_name}",
                    f"{path}.fields.{field_name}.cardinality",
                )
            )
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


def _declares_sensitivity(spec: dict[str, Any]) -> bool:
    return bool(spec.get("sensitivity") or spec.get("classification") or spec.get("pii") is not None)


def _validate_forbidden_patterns(field_name: str, spec: dict[str, Any], value: Any, event: dict[str, Any], contract_path: str, event_path: str) -> list[Finding]:
    patterns = spec.get("forbidden_patterns") or []
    if isinstance(patterns, (str, dict)):
        patterns = [patterns]
    if not isinstance(patterns, list) or not isinstance(value, str):
        return []
    findings: list[Finding] = []
    for index, pattern_spec in enumerate(patterns):
        label = f"forbidden_patterns[{index}]"
        pattern = pattern_spec
        if isinstance(pattern_spec, dict):
            label = str(pattern_spec.get("name", label))
            pattern = pattern_spec.get("pattern", pattern_spec.get("regex"))
        elif isinstance(pattern_spec, str) and pattern_spec in BUILTIN_FORBIDDEN_PATTERNS:
            label = pattern_spec
            pattern = BUILTIN_FORBIDDEN_PATTERNS[pattern_spec]
        if not isinstance(pattern, str):
            continue
        try:
            if re.search(pattern, value):
                findings.append(
                    Finding(
                        "error",
                        "telemetry.forbidden_pattern",
                        f"field '{field_name}' matched forbidden pattern '{label}'",
                        event_path,
                        contract_path,
                        _event_index(event),
                        {"pattern": label, "value_preview": _preview(value)},
                    )
                )
        except re.error as exc:
            findings.append(Finding("error", "contract.invalid_regex", f"invalid forbidden regex for field '{field_name}': {exc}", contract_path))
    return findings


def _validate_sensitive_value(field_name: str, spec: dict[str, Any], value: Any, event: dict[str, Any], contract_path: str, event_path: str) -> list[Finding]:
    if not isinstance(value, str):
        return []
    declared = _declares_sensitivity(spec)
    sensitivity = str(spec.get("sensitivity") or spec.get("classification") or "").lower()
    looks_sensitive = bool(SENSITIVE_FIELD_NAMES.search(field_name) or RAW_SECRET_VALUE.search(value))
    if not looks_sensitive:
        return []
    if not declared:
        return [
            Finding(
                "warning",
                "telemetry.sensitive_unclassified",
                f"field '{field_name}' appears sensitive but is not classified in the contract",
                event_path,
                contract_path,
                _event_index(event),
                {"value_preview": _preview(value)},
            )
        ]
    if spec.get("allow_raw_sensitive") is True or sensitivity in {"public", "none"}:
        return []
    if RAW_SECRET_VALUE.search(value):
        return [
            Finding(
                "error",
                "telemetry.sensitive_value",
                f"field '{field_name}' appears to contain raw {sensitivity or 'sensitive'} data",
                event_path,
                contract_path,
                _event_index(event),
                {"sensitivity": sensitivity or "unspecified", "value_preview": _preview(value)},
            )
        ]
    return []


def _preview(value: str) -> str:
    if len(value) <= 12:
        return "<redacted>"
    return f"{value[:4]}…{value[-4:]}"


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
