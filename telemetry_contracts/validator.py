from __future__ import annotations

import re
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any

from .findings import Finding
from .schema import validate_contract_schema

SignalKind = str
PRIMITIVE_TYPES = {"string", "integer", "number", "boolean", "object", "array", "null"}
SEVERITY_RANKS = {
    "TRACE": 10,
    "TRACE2": 11,
    "TRACE3": 12,
    "TRACE4": 13,
    "DEBUG": 20,
    "DEBUG2": 21,
    "DEBUG3": 22,
    "DEBUG4": 23,
    "INFO": 30,
    "INFO2": 31,
    "INFO3": 32,
    "INFO4": 33,
    "WARN": 40,
    "WARNING": 40,
    "WARN2": 41,
    "WARN3": 42,
    "WARN4": 43,
    "ERROR": 50,
    "ERROR2": 51,
    "ERROR3": 52,
    "ERROR4": 53,
    "FATAL": 60,
    "CRITICAL": 60,
    "FATAL2": 61,
    "FATAL3": 62,
    "FATAL4": 63,
}

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
    findings: list[Finding] = validate_contract_schema(contract)
    if contract.get("version") not in {"1", "1.0", 1}:
        findings.append(Finding("warning", "contract.version", "contract version should be 1", "$.version"))
    if not isinstance(contract.get("service"), str) or not contract.get("service"):
        findings.append(Finding("error", "contract.service", "contract must declare a non-empty service", "$.service"))
    findings.extend(_validate_field_definitions_shape(contract))
    for section in ("spans", "metrics", "logs"):
        if section in contract and not isinstance(contract[section], list):
            findings.append(Finding("error", "contract.section_type", f"{section} must be a list", f"$.{section}"))
            continue
        raw_signals = contract.get(section, []) or []
        if not isinstance(raw_signals, list):
            continue
        seen_signal_names: dict[str, int] = {}
        for signal_index, spec in enumerate(raw_signals):
            signal_path = f"$.{section}[{signal_index}]"
            if not isinstance(spec, dict):
                findings.append(Finding("error", "contract.signal_type", f"{section}[{signal_index}] must be an object", signal_path))
                continue
            if not isinstance(spec.get("name"), str) or not spec.get("name"):
                findings.append(Finding("error", "contract.signal_name", "signal must declare a non-empty name", f"{signal_path}.name"))
            elif spec["name"] in seen_signal_names:
                findings.append(
                    Finding(
                        "error",
                        "contract.duplicate_signal",
                        f"{section} signal '{spec['name']}' is declared more than once",
                        f"{signal_path}.name",
                        f"$.{section}[{seen_signal_names[spec['name']]}].name",
                    )
                )
            else:
                seen_signal_names[spec["name"]] = signal_index
            if "required" in spec and not isinstance(spec["required"], bool):
                findings.append(Finding("error", "contract.required_type", "signal required flag must be a boolean", f"{signal_path}.required"))
            if section == "metrics" and isinstance(spec.get("value"), dict):
                value_spec = _resolve_contract_field_spec("value", spec["value"], contract, f"{signal_path}.value", findings)
                findings.extend(_validate_field_spec("value", value_spec, f"{signal_path}.value"))
            if section == "logs" and spec.get("message_pattern") is not None:
                findings.extend(_validate_regex(str(spec["message_pattern"]), f"{signal_path}.message_pattern", "invalid log message regex"))
            if section == "logs":
                findings.extend(_validate_severity_policy_shape(spec, signal_path))
            findings.extend(_validate_conditional_requirement_shape(spec, signal_path))
            findings.extend(_validate_duplicate_field_names(spec, signal_path))
            for container in ("fields", "attributes", "tags"):
                raw_fields = spec.get(container, {}) or {}
                if not isinstance(raw_fields, dict):
                    findings.append(Finding("error", "contract.section_type", f"{container} must be an object", f"{signal_path}.{container}"))
                    continue
                for field_name, field_spec in raw_fields.items():
                    field_path = f"{signal_path}.{container}.{field_name}"
                    normalized_spec = _resolve_contract_field_spec(str(field_name), field_spec, contract, field_path, findings)
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
    findings.extend(_validate_correlation_policy_shape(contract.get("correlation")))
    findings.extend(_validate_temporal_sequences_shape(contract.get("temporal_sequences")))
    return findings


def _validate_duplicate_field_names(spec: dict[str, Any], signal_path: str) -> list[Finding]:
    findings: list[Finding] = []
    seen: dict[str, str] = {}
    for container in ("fields", "attributes", "tags"):
        raw_fields = spec.get(container, {}) or {}
        if not isinstance(raw_fields, dict):
            continue
        for field_name in raw_fields:
            field_key = str(field_name)
            field_path = f"{signal_path}.{container}.{field_key}"
            if field_key in seen:
                findings.append(
                    Finding(
                        "error",
                        "contract.duplicate_field",
                        f"field '{field_key}' is declared in multiple containers for signal '{spec.get('name')}'",
                        field_path,
                        seen[field_key],
                    )
                )
            else:
                seen[field_key] = field_path
    return findings


def _validate_conditional_requirement_shape(spec: dict[str, Any], signal_path: str) -> list[Finding]:
    raw_requirements = spec.get("conditional_requirements", []) or []
    if not isinstance(raw_requirements, list):
        return [Finding("error", "contract.conditional_requirement", "conditional_requirements must be an array", f"{signal_path}.conditional_requirements")]
    findings: list[Finding] = []
    for index, requirement in enumerate(raw_requirements):
        req_path = f"{signal_path}.conditional_requirements[{index}]"
        if not isinstance(requirement, dict):
            findings.append(Finding("error", "contract.conditional_requirement", "conditional requirement must be an object", req_path))
            continue
        condition = requirement.get("if")
        then = requirement.get("then")
        if not isinstance(condition, dict):
            findings.append(Finding("error", "contract.conditional_requirement", "conditional requirement must include an if object", f"{req_path}.if"))
        else:
            field = condition.get("field")
            if not isinstance(field, str) or not field:
                findings.append(Finding("error", "contract.conditional_requirement", "conditional if.field must be a non-empty string", f"{req_path}.if.field"))
            if "present" in condition and not isinstance(condition["present"], bool):
                findings.append(Finding("error", "contract.conditional_requirement", "conditional if.present must be a boolean", f"{req_path}.if.present"))
            if "allowed_values" in condition and not isinstance(condition["allowed_values"], list):
                findings.append(Finding("error", "contract.conditional_requirement", "conditional if.allowed_values must be an array", f"{req_path}.if.allowed_values"))
        if not isinstance(then, dict):
            findings.append(Finding("error", "contract.conditional_requirement", "conditional requirement must include a then object", f"{req_path}.then"))
        else:
            fields = then.get("fields", [])
            if not isinstance(fields, list) or not fields or not all(isinstance(field, str) and field for field in fields):
                findings.append(Finding("error", "contract.conditional_requirement", "conditional then.fields must be a non-empty array of strings", f"{req_path}.then.fields"))
    return findings



def _validate_field_definitions_shape(contract: dict[str, Any]) -> list[Finding]:
    definitions = contract.get("field_definitions")
    if definitions is None:
        return []
    if not isinstance(definitions, dict):
        return [Finding("error", "contract.field_definitions", "field_definitions must be an object", "$.field_definitions")]
    findings: list[Finding] = []
    for name, raw_spec in definitions.items():
        path = f"$.field_definitions.{name}"
        spec = _resolve_contract_field_spec(str(name), raw_spec, contract, path, findings)
        findings.extend(_validate_field_spec(str(name), spec, path))
    return findings


def _field_definitions(contract: dict[str, Any]) -> dict[str, Any]:
    definitions = contract.get("field_definitions", {})
    return definitions if isinstance(definitions, dict) else {}


def _reference_name(ref: str) -> str:
    prefixes = ("#/field_definitions/", "#/definitions/fields/", "field_definitions.")
    for prefix in prefixes:
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def _resolve_contract_field_spec(
    field_name: str,
    raw_spec: Any,
    contract: dict[str, Any],
    path: str,
    findings: list[Finding] | None = None,
    seen: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not isinstance(raw_spec, dict):
        return {"type": str(raw_spec)}
    ref = raw_spec.get("$ref", raw_spec.get("ref"))
    if ref is None:
        return dict(raw_spec)
    ref_name = _reference_name(str(ref))
    definitions = _field_definitions(contract)
    if ref_name in seen:
        if findings is not None:
            findings.append(Finding("error", "contract.field_ref_cycle", f"field reference cycle includes '{ref_name}'", path))
        return {key: value for key, value in raw_spec.items() if key not in {"$ref", "ref"}}
    if ref_name not in definitions:
        if findings is not None:
            findings.append(Finding("error", "contract.field_ref", f"field '{field_name}' references unknown field definition '{ref_name}'", path))
        return {key: value for key, value in raw_spec.items() if key not in {"$ref", "ref"}}
    base = _resolve_contract_field_spec(ref_name, definitions[ref_name], contract, f"$.field_definitions.{ref_name}", findings, (*seen, ref_name))
    overrides = {key: value for key, value in raw_spec.items() if key not in {"$ref", "ref"}}
    return {**base, **overrides}


def _validate_severity_policy_shape(spec: dict[str, Any], signal_path: str) -> list[Finding]:
    policy = spec.get("severity_policy")
    if policy is None:
        return []
    if not isinstance(policy, dict):
        return [Finding("error", "contract.severity_policy", "severity_policy must be an object", f"{signal_path}.severity_policy")]
    threshold = policy.get("min", policy.get("minimum"))
    if not isinstance(threshold, str) or _severity_rank(threshold) is None:
        return [Finding("error", "contract.severity_policy", "severity_policy.min must be a known severity", f"{signal_path}.severity_policy.min")]
    return []


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
            findings.extend(_validate_signal(kind, section, signal_index, spec, relevant_events, contract))
    findings.extend(_validate_correlation_policy(contract, relevant_events))
    findings.extend(_validate_temporal_sequences(contract, relevant_events))
    return findings


def _validate_correlation_policy_shape(policy: Any) -> list[Finding]:
    if policy is None or not isinstance(policy, dict):
        return []
    findings: list[Finding] = []
    keys = policy.get("keys")
    if not isinstance(keys, list) or not keys or not all(isinstance(key, str) and key for key in keys):
        findings.append(Finding("error", "contract.schema", "correlation.keys must be a non-empty array of strings", "$.correlation.keys"))
    require_on = policy.get("require_on", ["spans", "logs"])
    if not isinstance(require_on, list) or not require_on:
        findings.append(Finding("error", "contract.schema", "correlation.require_on must be a non-empty array", "$.correlation.require_on"))
    return findings


def _validate_correlation_policy(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    policy = contract.get("correlation")
    if not isinstance(policy, dict):
        return []
    keys = [key for key in policy.get("keys", []) if isinstance(key, str) and key]
    if not keys:
        return []
    required_kinds = [_normalize_signal_kind(item) for item in policy.get("require_on", ["spans", "logs"])]
    required_kinds = [kind for kind in required_kinds if kind in {"span", "log", "metric"}]
    if not required_kinds:
        return []
    declared_names = {
        "span": _declared_required_signal_names(contract, "spans"),
        "metric": _declared_required_signal_names(contract, "metrics"),
        "log": _declared_required_signal_names(contract, "logs"),
    }
    findings: list[Finding] = []
    values_by_kind: dict[str, set[tuple[str, Any]]] = {}
    for kind in required_kinds:
        kind_events = [
            event
            for event in events
            if event.get("kind") == kind and (not declared_names[kind] or event.get("name") in declared_names[kind])
        ]
        values: set[tuple[str, Any]] = set()
        for event in kind_events:
            event_values = _correlation_values(event, keys)
            if not event_values:
                findings.append(
                    Finding(
                        "error",
                        "telemetry.correlation_missing",
                        f"{kind} '{event.get('name')}' missing any correlation key from {keys}",
                        f"event[{_event_index(event)}]",
                        "$.correlation.keys",
                        _event_index(event),
                    )
                )
            values.update(event_values)
        if kind_events and not values:
            findings.append(Finding("error", "telemetry.correlation_missing", f"no {kind} events carried required correlation keys", f"events[{kind}]", "$.correlation.keys"))
        values_by_kind[kind] = values
    populated = [values for values in values_by_kind.values() if values]
    if len(populated) >= 2 and not set.intersection(*populated):
        findings.append(
            Finding(
                "error",
                "telemetry.correlation_mismatch",
                "required signal kinds do not share a correlation key/value pair",
                "events",
                "$.correlation",
                details={"kinds": required_kinds, "keys": keys},
            )
        )
    return findings


def _validate_temporal_sequences_shape(raw_sequences: Any) -> list[Finding]:
    if raw_sequences is None:
        return []
    if not isinstance(raw_sequences, list):
        return [Finding("error", "contract.temporal_sequence", "temporal_sequences must be an array", "$.temporal_sequences")]
    findings: list[Finding] = []
    for index, sequence in enumerate(raw_sequences):
        path = f"$.temporal_sequences[{index}]"
        if not isinstance(sequence, dict):
            findings.append(Finding("error", "contract.temporal_sequence", "temporal sequence must be an object", path))
            continue
        if sequence.get("id") is not None and not isinstance(sequence.get("id"), str):
            findings.append(Finding("error", "contract.temporal_sequence", "temporal sequence id must be a string", f"{path}.id"))
        if "window_ms" in sequence and (not isinstance(sequence["window_ms"], (int, float)) or isinstance(sequence["window_ms"], bool) or sequence["window_ms"] <= 0):
            findings.append(Finding("error", "contract.temporal_sequence", "temporal sequence window_ms must be a positive number", f"{path}.window_ms"))
        group_by = sequence.get("group_by", [])
        if group_by and (not isinstance(group_by, list) or not all(isinstance(item, str) and item for item in group_by)):
            findings.append(Finding("error", "contract.temporal_sequence", "temporal sequence group_by must be an array of strings", f"{path}.group_by"))
        steps = sequence.get("steps")
        if not isinstance(steps, list) or not steps:
            findings.append(Finding("error", "contract.temporal_sequence", "temporal sequence steps must be a non-empty array", f"{path}.steps"))
            continue
        for step_index, step in enumerate(steps):
            step_path = f"{path}.steps[{step_index}]"
            if not isinstance(step, dict):
                findings.append(Finding("error", "contract.temporal_sequence", "temporal sequence step must be an object", step_path))
                continue
            kind = _normalize_signal_kind(step.get("kind", step.get("signal")))
            if kind not in {"span", "log", "metric"}:
                findings.append(Finding("error", "contract.temporal_sequence", "temporal sequence step kind must be span, log, or metric", f"{step_path}.kind"))
            if not isinstance(step.get("name"), str) or not step.get("name"):
                findings.append(Finding("error", "contract.temporal_sequence", "temporal sequence step name must be a non-empty string", f"{step_path}.name"))
    return findings


def _validate_temporal_sequences(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    raw_sequences = contract.get("temporal_sequences", []) or []
    if not isinstance(raw_sequences, list):
        return []
    findings: list[Finding] = []
    for index, sequence in enumerate(raw_sequences):
        if not isinstance(sequence, dict) or sequence.get("required", True) is False:
            continue
        steps = sequence.get("steps")
        if not isinstance(steps, list) or not steps:
            continue
        normalized_steps = [step for step in steps if isinstance(step, dict)]
        if len(normalized_steps) != len(steps):
            continue
        path = f"$.temporal_sequences[{index}]"
        groups = _temporal_groups(events, sequence.get("group_by", []), normalized_steps)
        if not groups:
            findings.append(Finding("error", "telemetry.temporal_missing_step", _temporal_message(sequence, "no events matched the required temporal sequence"), "events", path, details={"sequence": sequence.get("id", index)}))
            continue
        for group_key, group_events in groups.items():
            findings.extend(_validate_temporal_group(sequence, normalized_steps, group_key, group_events, path))
    return findings


def _temporal_groups(events: list[dict[str, Any]], group_by: Any, steps: list[dict[str, Any]]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    keys = group_by if isinstance(group_by, list) and all(isinstance(item, str) for item in group_by) else []
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if not any(_event_matches_step(event, step) for step in steps):
            continue
        if keys:
            values: list[Any] = []
            missing = False
            for key in keys:
                value, _ = _lookup_field(event, key)
                if value is _MISSING:
                    missing = True
                    break
                values.append(value)
            if missing:
                continue
            group_key = tuple(values)
        else:
            group_key = ("__all__",)
        groups[group_key].append(event)
    return groups


def _validate_temporal_group(sequence: dict[str, Any], steps: list[dict[str, Any]], group_key: tuple[Any, ...], events: list[dict[str, Any]], path: str) -> list[Finding]:
    timed_events = [(event, _event_timestamp_ms(event)) for event in events]
    matched: list[tuple[dict[str, Any], float]] = []
    cursor = float("-inf")
    for step_index, step in enumerate(steps):
        candidates = [
            (event, timestamp)
            for event, timestamp in timed_events
            if timestamp is not None and timestamp >= cursor and _event_matches_step(event, step)
        ]
        if not candidates:
            code = "telemetry.temporal_order" if any(_event_matches_step(event, step) for event in events) else "telemetry.temporal_missing_step"
            return [Finding("error", code, _temporal_message(sequence, f"missing ordered step {step_index + 1} {step.get('name')!r}"), "events", f"{path}.steps[{step_index}]", details={"group": group_key})]
        event, timestamp = min(candidates, key=lambda item: item[1])
        matched.append((event, timestamp))
        cursor = timestamp
    window_ms = sequence.get("window_ms")
    if isinstance(window_ms, (int, float)) and not isinstance(window_ms, bool) and matched[-1][1] - matched[0][1] > window_ms:
        return [Finding("error", "telemetry.temporal_window", _temporal_message(sequence, f"sequence exceeded {window_ms}ms window"), "events", f"{path}.window_ms", details={"group": group_key, "elapsed_ms": matched[-1][1] - matched[0][1]})]
    return []


def _event_matches_step(event: dict[str, Any], step: dict[str, Any]) -> bool:
    return event.get("kind") == _normalize_signal_kind(step.get("kind", step.get("signal"))) and event.get("name") == step.get("name")


def _event_timestamp_ms(event: dict[str, Any]) -> float | None:
    for key in ("timestamp_ms", "time_ms", "start_time_ms", "end_time_ms"):
        value = event.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    for key in ("time_unix_nano", "start_time_unix_nano", "end_time_unix_nano"):
        value = event.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value) / 1_000_000
    value = event.get("timestamp") or event.get("time")
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp() * 1000
        except ValueError:
            return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _temporal_message(sequence: dict[str, Any], problem: str) -> str:
    label = sequence.get("id") if isinstance(sequence.get("id"), str) else "temporal sequence"
    return f"{label}: {problem}"



def _normalize_signal_kind(section_or_kind: Any) -> str:
    return {"spans": "span", "logs": "log", "metrics": "metric"}.get(str(section_or_kind), str(section_or_kind))


def _declared_required_signal_names(contract: dict[str, Any], section: str) -> set[str]:
    names: set[str] = set()
    for spec in contract.get(section, []) or []:
        if isinstance(spec, dict) and spec.get("required", True) and isinstance(spec.get("name"), str):
            names.add(spec["name"])
    return names


def _correlation_values(event: dict[str, Any], keys: list[str]) -> set[tuple[str, Any]]:
    values: set[tuple[str, Any]] = set()
    for key in keys:
        value, _ = _lookup_field(event, key)
        if value is not _MISSING and isinstance(value, (str, int, float, bool)):
            values.add((key, value))
    return values


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


def _validate_signal(kind: str, section: str, signal_index: int, spec: dict[str, Any], events: list[dict[str, Any]], contract: dict[str, Any]) -> list[Finding]:
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
        value_spec = _resolve_contract_field_spec("value", spec["value"], contract, f"{path}.value")
        for event in matches:
            findings.extend(_validate_field("value", value_spec, event.get("value"), event, f"{path}.value"))
    field_specs = _field_specs(spec, contract)
    for event in matches:
        for field_name, field_spec in field_specs.items():
            value, value_path = _lookup_field(event, field_name)
            if value is _MISSING:
                if field_spec.get("required", True):
                    findings.append(Finding("error", "telemetry.missing_field", f"{kind} '{name}' missing required field '{field_name}'", value_path, f"{path}.fields.{field_name}", _event_index(event)))
                continue
            findings.extend(_validate_field(field_name, field_spec, value, event, f"{path}.fields.{field_name}"))
        findings.extend(_validate_conditional_requirements(kind, name, spec, event, path))
    findings.extend(_validate_cardinality(kind, name, field_specs, matches, path))
    return findings


def _validate_conditional_requirements(kind: str, name: str, spec: dict[str, Any], event: dict[str, Any], path: str) -> list[Finding]:
    raw_requirements = spec.get("conditional_requirements", []) or []
    if not isinstance(raw_requirements, list):
        return []
    findings: list[Finding] = []
    for index, requirement in enumerate(raw_requirements):
        if not isinstance(requirement, dict):
            continue
        condition = requirement.get("if")
        then = requirement.get("then")
        if not isinstance(condition, dict) or not isinstance(then, dict):
            continue
        if not _condition_matches(condition, event):
            continue
        fields = then.get("fields", [])
        if not isinstance(fields, list):
            continue
        for field_position, field_name in enumerate(fields):
            if not isinstance(field_name, str) or not field_name:
                continue
            value, value_path = _lookup_field(event, field_name)
            if value is _MISSING:
                findings.append(
                    Finding(
                        "error",
                        "telemetry.conditional_missing_field",
                        f"{kind} '{name}' missing conditionally required field '{field_name}'",
                        value_path,
                        f"{path}.conditional_requirements[{index}].then.fields[{field_position}]",
                        _event_index(event),
                        {"condition": condition},
                    )
                )
    return findings


def _condition_matches(condition: dict[str, Any], event: dict[str, Any]) -> bool:
    field = condition.get("field")
    if not isinstance(field, str) or not field:
        return False
    value, _ = _lookup_field(event, field)
    is_present = value is not _MISSING
    if "present" in condition and condition["present"] is not is_present:
        return False
    if "equals" in condition:
        return is_present and value == condition["equals"]
    allowed_values = condition.get("allowed_values")
    if isinstance(allowed_values, list):
        return is_present and value in allowed_values
    return is_present if "present" not in condition else True


def _field_specs(spec: dict[str, Any], contract: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for container in ("fields", "attributes", "tags"):
        raw = spec.get(container, {}) or {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                merged[key] = _resolve_contract_field_spec(str(key), value, contract or {}, f"$.fields.{key}")
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
    severity_policy = spec.get("severity_policy")
    minimum_severity = None
    if isinstance(severity_policy, dict):
        threshold = severity_policy.get("min", severity_policy.get("minimum"))
        if isinstance(threshold, str):
            minimum_severity = threshold
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
        if minimum_severity is not None:
            expected_rank = _severity_rank(minimum_severity)
            actual = event.get("severity")
            actual_rank = _severity_rank(actual)
            if expected_rank is not None and (actual_rank is None or actual_rank < expected_rank):
                findings.append(
                    Finding(
                        "error",
                        "telemetry.log_severity_min",
                        f"log '{spec.get('name')}' severity must be at least {minimum_severity}",
                        f"event[{_event_index(event)}].severity",
                        f"{path}.severity_policy.min",
                        _event_index(event),
                        {"actual": actual, "minimum": minimum_severity},
                    )
                )
    return findings


def _severity_rank(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    if normalized.isdigit():
        return int(normalized)
    return SEVERITY_RANKS.get(normalized)
