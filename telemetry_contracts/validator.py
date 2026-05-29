from __future__ import annotations

import re
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any

from .findings import Finding
from .schema import validate_contract_schema

SignalKind = str
PRIMITIVE_TYPES = {"string", "integer", "number", "boolean", "object", "array", "null"}
ALLOWED_PRIVACY_TRANSFORMATIONS = {"raw", "redacted", "hashed", "tokenized", "bucketed", "omitted"}
PRIVACY_PUBLIC_CLASSES = {"public", "none", "non_sensitive", "non-sensitive"}
UNIT_KINDS: dict[str, str] = {
    "ns": "duration",
    "us": "duration",
    "µs": "duration",
    "ms": "duration",
    "s": "duration",
    "seconds": "duration",
    "minutes": "duration",
    "bytes": "bytes",
    "byte": "bytes",
    "kb": "bytes",
    "mb": "bytes",
    "gb": "bytes",
    "percent": "percent",
    "%": "percent",
    "ratio": "ratio",
    "count": "count",
    "timestamp_ms": "timestamp",
    "timestamp_unix_nano": "timestamp",
    "iso8601": "timestamp",
    "usd": "currency",
    "cents": "currency",
    "currency": "currency",
}
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
    findings.extend(_validate_policy_stubs_shape(contract.get("metadata")))
    findings.extend(_validate_privacy_classifications_shape(contract.get("privacy_classifications")))
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
                    findings.extend(_validate_field_spec(str(field_name), normalized_spec, field_path, contract))
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
    findings.extend(_validate_temporal_properties_shape(contract.get("temporal_properties")))
    findings.extend(_validate_hyperproperties_shape(contract.get("hyperproperties")))
    findings.extend(_validate_alternative_obligations_shape(contract.get("alternative_obligations")))
    from .assume_guarantee import validate_assume_guarantee_shape

    findings.extend(validate_assume_guarantee_shape(contract))
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


def _validate_policy_stubs_shape(metadata: Any) -> list[Finding]:
    if metadata is None:
        return []
    if not isinstance(metadata, dict):
        return [Finding("error", "contract.policy_stub", "metadata must be an object", "$.metadata")]
    findings: list[Finding] = []
    sampling = metadata.get("sampling")
    if sampling is not None:
        if not isinstance(sampling, dict):
            findings.append(Finding("error", "contract.policy_stub", "metadata.sampling must be an object keyed by traces, metrics, or logs", "$.metadata.sampling"))
        else:
            for signal, policy in sampling.items():
                path = f"$.metadata.sampling.{signal}"
                if signal not in {"traces", "spans", "metrics", "logs"}:
                    findings.append(Finding("error", "contract.policy_stub", f"sampling policy '{signal}' must target traces/spans, metrics, or logs", path))
                    continue
                if not isinstance(policy, dict):
                    findings.append(Finding("error", "contract.policy_stub", f"sampling policy '{signal}' must be an object", path))
                    continue
                rate = policy.get("minimum_rate", policy.get("rate"))
                if rate is not None and (not isinstance(rate, (int, float)) or isinstance(rate, bool) or rate < 0 or rate > 1):
                    findings.append(Finding("error", "contract.policy_stub", f"sampling policy '{signal}' rate must be between 0 and 1", f"{path}.minimum_rate"))
                strategy = policy.get("strategy")
                if strategy is not None and strategy not in {"always_on", "always_off", "parent_based", "probabilistic", "tail_based", "rate_limited"}:
                    findings.append(Finding("error", "contract.policy_stub", f"sampling policy '{signal}' has unknown strategy {strategy!r}", f"{path}.strategy"))
                for key in ("always_sample_errors", "always_keep_errors"):
                    if key in policy and not isinstance(policy[key], bool):
                        findings.append(Finding("error", "contract.policy_stub", f"sampling policy '{signal}' {key} must be boolean", f"{path}.{key}"))
    retention = metadata.get("retention")
    if retention is not None:
        if not isinstance(retention, dict):
            findings.append(Finding("error", "contract.policy_stub", "metadata.retention must be an object with day counts", "$.metadata.retention"))
        else:
            for key, value in retention.items():
                if key not in {"traces_days", "spans_days", "metrics_days", "logs_days"}:
                    findings.append(Finding("error", "contract.policy_stub", f"retention key '{key}' is not recognized", f"$.metadata.retention.{key}"))
                elif not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                    findings.append(Finding("error", "contract.policy_stub", f"retention {key} must be a positive integer day count", f"$.metadata.retention.{key}"))
    findings.extend(_validate_strict_policy_shape(metadata.get("strict_validation")))
    return findings


def _validate_strict_policy_shape(policy: Any) -> list[Finding]:
    if policy is None:
        return []
    if not isinstance(policy, dict):
        return [Finding("error", "contract.strict_policy", "metadata.strict_validation must be an object", "$.metadata.strict_validation")]
    findings: list[Finding] = []
    if "enabled" in policy and not isinstance(policy["enabled"], bool):
        findings.append(Finding("error", "contract.strict_policy", "strict_validation.enabled must be boolean", "$.metadata.strict_validation.enabled"))
    if "allow_all_extra_fields" in policy and not isinstance(policy["allow_all_extra_fields"], bool):
        findings.append(Finding("error", "contract.strict_policy", "strict_validation.allow_all_extra_fields must be boolean", "$.metadata.strict_validation.allow_all_extra_fields"))
    for key in ("allow_unmodeled_services", "allow_collector_transformations"):
        if key in policy and (not isinstance(policy[key], list) or not all(isinstance(item, str) and item for item in policy[key])):
            findings.append(Finding("error", "contract.strict_policy", f"strict_validation.{key} must be an array of strings", f"$.metadata.strict_validation.{key}"))
    for key in ("allow_undeclared_signals", "allow_unexpected_fields", "allowed_extra_fields"):
        if key not in policy:
            continue
        raw = policy[key]
        if not isinstance(raw, list):
            findings.append(Finding("error", "contract.strict_policy", f"strict_validation.{key} must be an array", f"$.metadata.strict_validation.{key}"))
            continue
        for index, item in enumerate(raw):
            item_path = f"$.metadata.strict_validation.{key}[{index}]"
            if isinstance(item, str) and item:
                continue
            if not isinstance(item, dict):
                findings.append(Finding("error", "contract.strict_policy", f"strict_validation.{key} entries must be strings or objects", item_path))
                continue
            kind = item.get("kind", item.get("signal"))
            if kind is not None and _normalize_signal_kind(kind) not in {"span", "log", "metric"}:
                findings.append(Finding("error", "contract.strict_policy", "strict escape hatch kind must be span, log, or metric", f"{item_path}.kind"))
            if "name" in item and (not isinstance(item["name"], str) or not item["name"]):
                findings.append(Finding("error", "contract.strict_policy", "strict escape hatch name must be a non-empty string", f"{item_path}.name"))
            fields = item.get("fields")
            if fields is not None and (not isinstance(fields, list) or not all(isinstance(field, str) and field for field in fields)):
                findings.append(Finding("error", "contract.strict_policy", "strict escape hatch fields must be an array of strings", f"{item_path}.fields"))
            if "field" in item and (not isinstance(item["field"], str) or not item["field"]):
                findings.append(Finding("error", "contract.strict_policy", "strict escape hatch field must be a non-empty string", f"{item_path}.field"))
    return findings


def _validate_privacy_classifications_shape(raw_policy: Any) -> list[Finding]:
    if raw_policy is None:
        return []
    if not isinstance(raw_policy, dict):
        return [Finding("error", "contract.privacy_policy", "privacy_classifications must be an object", "$.privacy_classifications")]
    findings: list[Finding] = []
    for name, policy in raw_policy.items():
        path = f"$.privacy_classifications.{name}"
        if not isinstance(name, str) or not name:
            findings.append(Finding("error", "contract.privacy_policy", "privacy classification names must be non-empty strings", path))
        if not isinstance(policy, dict):
            findings.append(Finding("error", "contract.privacy_policy", f"privacy classification '{name}' must be an object", path))
            continue
        transformations = policy.get("allowed_transformations")
        if not isinstance(transformations, list) or not transformations:
            findings.append(Finding("error", "contract.privacy_policy", f"privacy classification '{name}' must declare allowed_transformations", f"{path}.allowed_transformations"))
            continue
        bad = [item for item in transformations if item not in ALLOWED_PRIVACY_TRANSFORMATIONS]
        if bad:
            findings.append(Finding("error", "contract.privacy_policy", f"privacy classification '{name}' has unknown transformations {bad!r}", f"{path}.allowed_transformations"))
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
        findings.extend(_validate_field_spec(str(name), spec, path, contract))
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


def validate_events(contract: dict[str, Any], events: list[dict[str, Any]], *, strict: bool | None = None) -> list[Finding]:
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
    findings.extend(_validate_temporal_properties(contract, relevant_events))
    findings.extend(_validate_hyperproperties(contract, relevant_events))
    from .alternatives import alternative_obligation_findings

    findings.extend(alternative_obligation_findings(contract, relevant_events))
    if _strict_enabled(contract, strict):
        findings.extend(_validate_strict_events(contract, events))
    return findings


def _strict_enabled(contract: dict[str, Any], strict: bool | None) -> bool:
    if strict is not None:
        return strict
    metadata = contract.get("metadata")
    policy = metadata.get("strict_validation") if isinstance(metadata, dict) else None
    return isinstance(policy, dict) and policy.get("enabled") is True


def _strict_policy(contract: dict[str, Any]) -> dict[str, Any]:
    metadata = contract.get("metadata")
    policy = metadata.get("strict_validation") if isinstance(metadata, dict) else None
    return policy if isinstance(policy, dict) else {}


def _validate_strict_events(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    service = contract.get("service")
    policy = _strict_policy(contract)
    allowed_services = {service} if isinstance(service, str) and service else set()
    allowed_services.update(str(item) for item in policy.get("allow_unmodeled_services", []) if isinstance(item, str))
    declared = _declared_signal_names(contract)
    findings: list[Finding] = []
    for event in events:
        event_service = event.get("service")
        if allowed_services and event_service not in allowed_services:
            findings.append(
                Finding(
                    "error",
                    "telemetry.strict_unmodeled_service",
                    f"event service {event_service!r} is not modeled by contract service {service!r}",
                    f"event[{_event_index(event)}].service",
                    "$.service",
                    _event_index(event),
                    {"service": event_service, "allowed_services": sorted(allowed_services)},
                )
            )
            continue
        if isinstance(service, str) and event_service != service:
            continue
        kind = _normalize_signal_kind(event.get("kind"))
        name = event.get("name")
        if kind not in {"span", "log", "metric"} or not isinstance(name, str):
            continue
        if name not in declared.get(kind, set()):
            if _strict_signal_allowed(policy, kind, name):
                continue
            findings.append(
                Finding(
                    "error",
                    "telemetry.strict_undeclared_signal",
                    f"{kind} '{name}' is not declared by the contract",
                    f"event[{_event_index(event)}].name",
                    f"$.{kind}s",
                    _event_index(event),
                    {"kind": kind, "name": name},
                )
            )
            continue
        findings.extend(_validate_strict_event_fields(contract, policy, event, kind, name))
        findings.extend(_validate_strict_transformations(contract, policy, event))
    return findings


def _declared_signal_names(contract: dict[str, Any]) -> dict[str, set[str]]:
    declared: dict[str, set[str]] = {"span": set(), "log": set(), "metric": set()}
    for section, kind in (("spans", "span"), ("logs", "log"), ("metrics", "metric")):
        for spec in contract.get(section, []) or []:
            if isinstance(spec, dict) and isinstance(spec.get("name"), str):
                declared[kind].add(spec["name"])
    for sequence in contract.get("temporal_sequences", []) or []:
        if isinstance(sequence, dict):
            for step in sequence.get("steps", []) or []:
                if isinstance(step, dict):
                    kind = _normalize_signal_kind(step.get("kind", step.get("signal")))
                    if kind in declared and isinstance(step.get("name"), str):
                        declared[kind].add(step["name"])
    for group in contract.get("alternative_obligations", []) or []:
        if isinstance(group, dict):
            for option in group.get("any_of", []) or []:
                if isinstance(option, dict):
                    kind = _normalize_signal_kind(option.get("signal", option.get("kind")))
                    if kind in declared and isinstance(option.get("name"), str):
                        declared[kind].add(option["name"])
    for scenario in contract.get("scenarios", []) or []:
        if isinstance(scenario, dict):
            for requirement in scenario.get("minimum_observations", scenario.get("requires", [])) or []:
                _collect_requirement_signal_names(requirement, declared)
    return declared


def _collect_requirement_signal_names(requirement: Any, declared: dict[str, set[str]]) -> None:
    if not isinstance(requirement, dict):
        return
    kind = _normalize_signal_kind(requirement.get("signal", requirement.get("kind")))
    if kind in declared and isinstance(requirement.get("name"), str):
        declared[kind].add(requirement["name"])
    for option in requirement.get("any_of", []) or []:
        if isinstance(option, dict):
            option_kind = _normalize_signal_kind(option.get("signal", option.get("kind")))
            if option_kind in declared and isinstance(option.get("name"), str):
                declared[option_kind].add(option["name"])


def _validate_strict_event_fields(contract: dict[str, Any], policy: dict[str, Any], event: dict[str, Any], kind: str, name: str) -> list[Finding]:
    if policy.get("allow_all_extra_fields") is True:
        return []
    expected = _expected_fields_for_signal(contract, kind, name)
    findings: list[Finding] = []
    for container in ("attributes", "tags", "fields"):
        values = event.get(container)
        if not isinstance(values, dict):
            continue
        for field_name in values:
            field_name = str(field_name)
            if field_name in expected or _strict_field_allowed(policy, kind, name, field_name):
                continue
            findings.append(
                Finding(
                    "error",
                    "telemetry.strict_unexpected_field",
                    f"{kind} '{name}' emitted undeclared field '{field_name}'",
                    f"event[{_event_index(event)}].{container}.{field_name}",
                    f"$.{kind}s[name={name}]",
                    _event_index(event),
                    {"kind": kind, "name": name, "field": field_name, "container": container},
                )
            )
    return findings


def _expected_fields_for_signal(contract: dict[str, Any], kind: str, name: str) -> set[str]:
    section = {"span": "spans", "log": "logs", "metric": "metrics"}[kind]
    expected: set[str] = set()
    for spec in contract.get(section, []) or []:
        if isinstance(spec, dict) and spec.get("name") == name:
            expected.update(_field_specs(spec, contract).keys())
            for requirement in spec.get("conditional_requirements", []) or []:
                if not isinstance(requirement, dict):
                    continue
                condition = requirement.get("if")
                if isinstance(condition, dict) and isinstance(condition.get("field"), str):
                    expected.add(condition["field"])
                then = requirement.get("then")
                fields = then.get("fields") if isinstance(then, dict) else None
                if isinstance(fields, list):
                    expected.update(str(field) for field in fields if isinstance(field, str))
            if kind == "metric" and isinstance(spec.get("value"), dict):
                expected.add("value")
    for group in contract.get("alternative_obligations", []) or []:
        if not isinstance(group, dict):
            continue
        for option in group.get("any_of", []) or []:
            if isinstance(option, dict) and _normalize_signal_kind(option.get("signal", option.get("kind"))) == kind and option.get("name") == name:
                expected.update(str(field) for field in option.get("fields", []) if isinstance(field, str))
    for scenario in contract.get("scenarios", []) or []:
        if isinstance(scenario, dict):
            for requirement in scenario.get("minimum_observations", scenario.get("requires", [])) or []:
                expected.update(_expected_fields_from_requirement(requirement, kind, name))
    return expected


def _expected_fields_from_requirement(requirement: Any, kind: str, name: str) -> set[str]:
    if not isinstance(requirement, dict):
        return set()
    expected: set[str] = set()
    if _normalize_signal_kind(requirement.get("signal", requirement.get("kind"))) == kind and requirement.get("name") == name:
        expected.update(str(field) for field in requirement.get("fields", []) if isinstance(field, str))
    for option in requirement.get("any_of", []) or []:
        if isinstance(option, dict) and _normalize_signal_kind(option.get("signal", option.get("kind"))) == kind and option.get("name") == name:
            expected.update(str(field) for field in option.get("fields", []) if isinstance(field, str))
    return expected


def _validate_strict_transformations(contract: dict[str, Any], policy: dict[str, Any], event: dict[str, Any]) -> list[Finding]:
    approved = set(str(item) for item in policy.get("allow_collector_transformations", []) if isinstance(item, str))
    metadata = contract.get("metadata")
    preservation = metadata.get("transformation_preservation") if isinstance(metadata, dict) else None
    if isinstance(preservation, dict):
        approved.update(str(item) for item in preservation.get("approved_transformations", []) if isinstance(item, str))
    findings = []
    for transformation in _event_transformations(event):
        if transformation in approved:
            continue
        findings.append(
            Finding(
                "error",
                "telemetry.strict_undocumented_transformation",
                f"collector transformation {transformation!r} is not documented by contract metadata",
                f"event[{_event_index(event)}].transformations",
                "$.metadata.transformation_preservation.approved_transformations",
                _event_index(event),
                {"transformation": transformation, "approved_transformations": sorted(approved)},
            )
        )
    return findings


def _event_transformations(event: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for key in ("transformation", "transformations", "collector_transformation", "collector_transformations"):
        value = event.get(key)
        if isinstance(value, str) and value:
            found.add(value)
        elif isinstance(value, list):
            found.update(str(item) for item in value if isinstance(item, str) and item)
    for container in ("attributes", "tags", "fields"):
        values = event.get(container)
        if not isinstance(values, dict):
            continue
        for key in ("transformation", "transformations", "collector_transformation", "collector_transformations"):
            value = values.get(key)
            if isinstance(value, str) and value:
                found.add(value)
            elif isinstance(value, list):
                found.update(str(item) for item in value if isinstance(item, str) and item)
    return found


def _strict_signal_allowed(policy: dict[str, Any], kind: str, name: str) -> bool:
    for item in policy.get("allow_undeclared_signals", []) or []:
        if isinstance(item, str):
            if item in {name, f"{kind}:{name}", f"{kind}s:{name}"}:
                return True
        elif isinstance(item, dict):
            item_kind = item.get("kind", item.get("signal"))
            if item_kind is not None and _normalize_signal_kind(item_kind) != kind:
                continue
            item_name = item.get("name")
            if item_name in {None, name}:
                return True
    return False


def _strict_field_allowed(policy: dict[str, Any], kind: str, name: str, field: str) -> bool:
    for key in ("allow_unexpected_fields", "allowed_extra_fields"):
        for item in policy.get(key, []) or []:
            if isinstance(item, str):
                if item in {field, f"{kind}:{name}:{field}", f"{kind}s:{name}:{field}"}:
                    return True
                continue
            if not isinstance(item, dict):
                continue
            item_kind = item.get("kind", item.get("signal"))
            if item_kind is not None and _normalize_signal_kind(item_kind) != kind:
                continue
            item_name = item.get("name")
            if item_name is not None and item_name != name:
                continue
            fields = item.get("fields")
            if isinstance(fields, list) and field in fields:
                return True
            if item.get("field") == field:
                return True
    return False


def _validate_alternative_obligations_shape(raw: Any) -> list[Finding]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return [Finding("error", "contract.alternative_obligation", "alternative_obligations must be a list", "$.alternative_obligations")]
    findings: list[Finding] = []
    seen_ids: dict[str, int] = {}
    for index, group in enumerate(raw):
        path = f"$.alternative_obligations[{index}]"
        if not isinstance(group, dict):
            findings.append(Finding("error", "contract.alternative_obligation", "alternative obligation must be an object", path))
            continue
        group_id = group.get("id")
        if not isinstance(group_id, str) or not group_id:
            findings.append(Finding("error", "contract.alternative_obligation", "alternative obligation must declare a non-empty id", f"{path}.id"))
        elif group_id in seen_ids:
            findings.append(Finding("error", "contract.alternative_obligation", f"alternative obligation '{group_id}' is declared more than once", f"{path}.id", f"$.alternative_obligations[{seen_ids[group_id]}].id"))
        else:
            seen_ids[group_id] = index
        if "required" in group and not isinstance(group["required"], bool):
            findings.append(Finding("error", "contract.required_type", "alternative obligation required flag must be a boolean", f"{path}.required"))
        options = group.get("any_of")
        if not isinstance(options, list) or not options:
            findings.append(Finding("error", "contract.alternative_obligation", "alternative obligation any_of must be a non-empty list", f"{path}.any_of"))
            continue
        for option_index, option in enumerate(options):
            option_path = f"{path}.any_of[{option_index}]"
            if not isinstance(option, dict):
                findings.append(Finding("error", "contract.alternative_obligation", "alternative option must be an object", option_path))
                continue
            signal = _normalize_signal_kind(option.get("signal", option.get("kind")))
            if signal not in {"span", "log", "metric"}:
                findings.append(Finding("error", "contract.alternative_obligation", "alternative option signal must be span, log, or metric", f"{option_path}.signal"))
            if not isinstance(option.get("name"), str) or not option.get("name"):
                findings.append(Finding("error", "contract.signal_name", "alternative option must declare a non-empty name", f"{option_path}.name"))
            fields = option.get("fields", [])
            if not isinstance(fields, list) or not all(isinstance(field, str) and field for field in fields):
                findings.append(Finding("error", "contract.alternative_obligation", "alternative option fields must be an array of non-empty strings", f"{option_path}.fields"))
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


TEMPORAL_PROPERTY_TYPES = {"safety", "bounded_response", "absence", "ordering", "deadline"}
HYPERPROPERTY_TYPES = {"pii_non_disclosure", "tenant_non_interference"}


def _validate_temporal_properties_shape(raw_properties: Any) -> list[Finding]:
    if raw_properties is None:
        return []
    if not isinstance(raw_properties, list):
        return [Finding("error", "contract.temporal_property", "temporal_properties must be an array", "$.temporal_properties")]
    findings: list[Finding] = []
    for index, prop in enumerate(raw_properties):
        path = f"$.temporal_properties[{index}]"
        if not isinstance(prop, dict):
            findings.append(Finding("error", "contract.temporal_property", "temporal property must be an object", path))
            continue
        if prop.get("id") is not None and not isinstance(prop.get("id"), str):
            findings.append(Finding("error", "contract.temporal_property", "temporal property id must be a string", f"{path}.id"))
        prop_type = prop.get("type")
        if prop_type not in TEMPORAL_PROPERTY_TYPES:
            findings.append(Finding("error", "contract.temporal_property", f"temporal property type must be one of {sorted(TEMPORAL_PROPERTY_TYPES)}", f"{path}.type"))
            continue
        group_by = prop.get("group_by", [])
        if group_by and (not isinstance(group_by, list) or not all(isinstance(item, str) and item for item in group_by)):
            findings.append(Finding("error", "contract.temporal_property", "temporal property group_by must be an array of strings", f"{path}.group_by"))
        if prop_type == "safety":
            findings.extend(_validate_temporal_selector_shape(prop.get("match"), f"{path}.match"))
            findings.extend(_validate_temporal_predicate_shape(prop.get("condition"), f"{path}.condition", required=True))
        elif prop_type == "absence":
            findings.extend(_validate_temporal_selector_shape(prop.get("forbidden"), f"{path}.forbidden"))
        elif prop_type == "bounded_response":
            findings.extend(_validate_temporal_selector_shape(prop.get("trigger"), f"{path}.trigger"))
            findings.extend(_validate_temporal_selector_shape(prop.get("response"), f"{path}.response"))
            findings.extend(_validate_positive_time_bound(prop, path, "within_ms"))
        elif prop_type == "ordering":
            findings.extend(_validate_temporal_selector_shape(prop.get("before"), f"{path}.before"))
            findings.extend(_validate_temporal_selector_shape(prop.get("after"), f"{path}.after"))
            if "allow_equal_timestamps" in prop and not isinstance(prop["allow_equal_timestamps"], bool):
                findings.append(Finding("error", "contract.temporal_property", "allow_equal_timestamps must be boolean", f"{path}.allow_equal_timestamps"))
        elif prop_type == "deadline":
            findings.extend(_validate_temporal_selector_shape(prop.get("match"), f"{path}.match"))
            if prop.get("start") is not None:
                findings.extend(_validate_temporal_selector_shape(prop.get("start"), f"{path}.start"))
            findings.extend(_validate_positive_time_bound(prop, path, "within_ms"))
    return findings


def _validate_hyperproperties_shape(raw_properties: Any) -> list[Finding]:
    if raw_properties is None:
        return []
    if not isinstance(raw_properties, list):
        return [Finding("error", "contract.hyperproperty", "hyperproperties must be an array", "$.hyperproperties")]
    findings: list[Finding] = []
    for index, prop in enumerate(raw_properties):
        path = f"$.hyperproperties[{index}]"
        if not isinstance(prop, dict):
            findings.append(Finding("error", "contract.hyperproperty", "hyperproperty must be an object", path))
            continue
        if prop.get("id") is not None and not isinstance(prop.get("id"), str):
            findings.append(Finding("error", "contract.hyperproperty", "hyperproperty id must be a string", f"{path}.id"))
        if "required" in prop and not isinstance(prop["required"], bool):
            findings.append(Finding("error", "contract.required_type", "hyperproperty required flag must be a boolean", f"{path}.required"))
        prop_type = prop.get("type")
        if prop_type not in HYPERPROPERTY_TYPES:
            findings.append(Finding("error", "contract.hyperproperty", f"hyperproperty type must be one of {sorted(HYPERPROPERTY_TYPES)}", f"{path}.type"))
            continue
        if prop_type == "pii_non_disclosure":
            fields = prop.get("sensitive_fields")
            if not isinstance(fields, list) or not fields or not all(isinstance(field, str) and field for field in fields):
                findings.append(Finding("error", "contract.hyperproperty", "pii_non_disclosure requires non-empty sensitive_fields", f"{path}.sensitive_fields"))
            sink_kinds = prop.get("sink_kinds", ["spans", "logs", "metrics"])
            if not isinstance(sink_kinds, list) or not all(_normalize_signal_kind(kind) in {"span", "log", "metric"} for kind in sink_kinds):
                findings.append(Finding("error", "contract.hyperproperty", "sink_kinds must contain span, log, or metric", f"{path}.sink_kinds"))
            patterns = prop.get("forbidden_patterns", [])
            findings.extend(_validate_forbidden_pattern_specs("hyperproperty", {"forbidden_patterns": patterns}, path))
        elif prop_type == "tenant_non_interference":
            tenant_field = prop.get("tenant_field", "tenant_id")
            if not isinstance(tenant_field, str) or not tenant_field:
                findings.append(Finding("error", "contract.hyperproperty", "tenant_non_interference tenant_field must be a non-empty string", f"{path}.tenant_field"))
            keys = prop.get("isolation_keys", ["trace_id", "request_id"])
            if not isinstance(keys, list) or not keys or not all(isinstance(key, str) and key for key in keys):
                findings.append(Finding("error", "contract.hyperproperty", "tenant_non_interference isolation_keys must be a non-empty string array", f"{path}.isolation_keys"))
    return findings


def _validate_temporal_selector_shape(selector: Any, path: str) -> list[Finding]:
    if not isinstance(selector, dict):
        return [Finding("error", "contract.temporal_property", "temporal selector must be an object", path)]
    findings: list[Finding] = []
    kind = _normalize_signal_kind(selector.get("kind", selector.get("signal")))
    if kind not in {"span", "log", "metric"}:
        findings.append(Finding("error", "contract.temporal_property", "temporal selector kind must be span, log, or metric", f"{path}.kind"))
    if not isinstance(selector.get("name"), str) or not selector.get("name"):
        findings.append(Finding("error", "contract.temporal_property", "temporal selector name must be a non-empty string", f"{path}.name"))
    findings.extend(_validate_temporal_predicate_shape(selector, path, required=False))
    return findings


def _validate_temporal_predicate_shape(predicate: Any, path: str, *, required: bool) -> list[Finding]:
    if predicate is None and not required:
        return []
    if not isinstance(predicate, dict):
        return [Finding("error", "contract.temporal_property", "temporal predicate must be an object", path)]
    findings: list[Finding] = []
    has_predicate = False
    if "field" in predicate:
        has_predicate = True
        if not isinstance(predicate.get("field"), str) or not predicate.get("field"):
            findings.append(Finding("error", "contract.temporal_property", "temporal predicate field must be a non-empty string", f"{path}.field"))
    for key in ("present",):
        if key in predicate:
            has_predicate = True
            if not isinstance(predicate[key], bool):
                findings.append(Finding("error", "contract.temporal_property", f"temporal predicate {key} must be boolean", f"{path}.{key}"))
    if "allowed_values" in predicate:
        has_predicate = True
        if not isinstance(predicate["allowed_values"], list):
            findings.append(Finding("error", "contract.temporal_property", "temporal predicate allowed_values must be an array", f"{path}.allowed_values"))
    for key in ("min", "max"):
        if key in predicate:
            has_predicate = True
            if not isinstance(predicate[key], (int, float)) or isinstance(predicate[key], bool):
                findings.append(Finding("error", "contract.temporal_property", f"temporal predicate {key} must be numeric", f"{path}.{key}"))
    if "pattern" in predicate:
        has_predicate = True
        if not isinstance(predicate["pattern"], str):
            findings.append(Finding("error", "contract.temporal_property", "temporal predicate pattern must be a string", f"{path}.pattern"))
        else:
            findings.extend(_validate_regex(predicate["pattern"], f"{path}.pattern", "invalid temporal predicate regex", code="contract.temporal_property"))
    if "equals" in predicate or "not_equals" in predicate:
        has_predicate = True
    if required and not has_predicate:
        findings.append(Finding("error", "contract.temporal_property", "temporal predicate must declare at least one field condition", path))
    if has_predicate and "field" not in predicate:
        findings.append(Finding("error", "contract.temporal_property", "temporal predicate with conditions must declare field", f"{path}.field"))
    return findings


def _validate_positive_time_bound(prop: dict[str, Any], path: str, key: str) -> list[Finding]:
    value = prop.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        return [Finding("error", "contract.temporal_property", f"temporal property {key} must be a positive number", f"{path}.{key}")]
    return []


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


def _validate_temporal_properties(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    raw_properties = contract.get("temporal_properties", []) or []
    if not isinstance(raw_properties, list):
        return []
    findings: list[Finding] = []
    for index, prop in enumerate(raw_properties):
        if not isinstance(prop, dict) or prop.get("required", True) is False:
            continue
        prop_type = prop.get("type")
        if prop_type not in TEMPORAL_PROPERTY_TYPES:
            continue
        path = f"$.temporal_properties[{index}]"
        if prop_type == "safety":
            findings.extend(_validate_temporal_property_safety(prop, events, path))
        elif prop_type == "absence":
            findings.extend(_validate_temporal_property_absence(prop, events, path))
        elif prop_type == "bounded_response":
            findings.extend(_validate_temporal_property_response(prop, events, path))
        elif prop_type == "ordering":
            findings.extend(_validate_temporal_property_ordering(prop, events, path))
        elif prop_type == "deadline":
            findings.extend(_validate_temporal_property_deadline(prop, events, path))
    return findings


def _validate_hyperproperties(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    raw_properties = contract.get("hyperproperties", []) or []
    if not isinstance(raw_properties, list):
        return []
    findings: list[Finding] = []
    for index, prop in enumerate(raw_properties):
        if not isinstance(prop, dict) or prop.get("required", True) is False:
            continue
        prop_type = prop.get("type")
        path = f"$.hyperproperties[{index}]"
        if prop_type == "pii_non_disclosure":
            findings.extend(_validate_hyper_pii_non_disclosure(prop, events, path))
        elif prop_type == "tenant_non_interference":
            findings.extend(_validate_hyper_tenant_non_interference(prop, events, path))
    return findings


def _validate_hyper_pii_non_disclosure(prop: dict[str, Any], events: list[dict[str, Any]], path: str) -> list[Finding]:
    sensitive_fields = [field for field in prop.get("sensitive_fields", []) if isinstance(field, str) and field]
    if not sensitive_fields:
        return []
    sink_kinds = {_normalize_signal_kind(kind) for kind in prop.get("sink_kinds", ["spans", "logs", "metrics"])}
    sink_kinds = {kind for kind in sink_kinds if kind in {"span", "log", "metric"}}
    patterns = _compiled_hyper_forbidden_patterns(prop.get("forbidden_patterns", []))
    findings: list[Finding] = []
    for event in events:
        if event.get("kind") not in sink_kinds:
            continue
        for field_name in sensitive_fields:
            value, value_path = _lookup_field(event, field_name)
            if value is _MISSING or value in (None, ""):
                continue
            if not isinstance(value, str):
                continue
            if _looks_privacy_preserved_value(value) or _field_or_event_declares_safe_transformation(event, field_name):
                continue
            pattern_match = any(pattern.search(value) for pattern in patterns)
            field_name_sensitive = bool(SENSITIVE_FIELD_NAMES.search(field_name))
            if not (pattern_match or field_name_sensitive):
                continue
            findings.append(
                Finding(
                    "error",
                    "telemetry.hyper_pii_disclosure",
                    _hyper_message(prop, f"{event.get('kind')} {event.get('name')!r} exposes raw sensitive field '{field_name}'"),
                    value_path,
                    f"{path}.sensitive_fields",
                    _event_index(event),
                    {
                        "property": prop.get("id"),
                        "field": field_name,
                        "value_preview": _preview(value),
                        "trace_id": _safe_lookup(event, "trace_id"),
                        "request_id": _safe_lookup(event, "request_id"),
                    },
                )
            )
    return findings


def _validate_hyper_tenant_non_interference(prop: dict[str, Any], events: list[dict[str, Any]], path: str) -> list[Finding]:
    tenant_field = prop.get("tenant_field", "tenant_id")
    keys = [key for key in prop.get("isolation_keys", ["trace_id", "request_id"]) if isinstance(key, str) and key]
    if not isinstance(tenant_field, str) or not tenant_field or not keys:
        return []
    findings: list[Finding] = []
    observations: list[dict[str, Any]] = []
    for event in events:
        tenant, tenant_path = _lookup_field(event, tenant_field)
        if tenant is _MISSING or tenant in (None, ""):
            continue
        isolation_values = {key: value for key in keys for value in [_safe_lookup(event, key)] if value not in (None, "")}
        if not isolation_values:
            continue
        observations.append({"event": event, "tenant": tenant, "tenant_path": tenant_path, "keys": isolation_values})
    seen_pairs: set[tuple[int | None, int | None, str, Any]] = set()
    for left_index, left in enumerate(observations):
        for right in observations[left_index + 1:]:
            if left["tenant"] == right["tenant"]:
                continue
            shared = [(key, value) for key, value in left["keys"].items() if right["keys"].get(key) == value]
            for key, value in shared:
                event_a = _event_index(left["event"])
                event_b = _event_index(right["event"])
                pair_key = (event_a, event_b, key, value)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                findings.append(
                    Finding(
                        "error",
                        "telemetry.hyper_tenant_interference",
                        _hyper_message(prop, f"tenants {left['tenant']!r} and {right['tenant']!r} share {key}={value!r}"),
                        f"event[{event_b}].{key}",
                        f"{path}.isolation_keys",
                        event_b,
                        {
                            "property": prop.get("id"),
                            "tenant_field": tenant_field,
                            "left_event_index": event_a,
                            "right_event_index": event_b,
                            "left_tenant": left["tenant"],
                            "right_tenant": right["tenant"],
                            "shared_key": key,
                            "shared_value": value,
                        },
                    )
                )
    return findings


def _compiled_hyper_forbidden_patterns(raw_patterns: Any) -> list[re.Pattern[str]]:
    patterns = raw_patterns or []
    if isinstance(patterns, (str, dict)):
        patterns = [patterns]
    compiled: list[re.Pattern[str]] = [RAW_SECRET_VALUE]
    if not isinstance(patterns, list):
        return compiled
    for pattern_spec in patterns:
        pattern = pattern_spec
        if isinstance(pattern_spec, dict):
            pattern = pattern_spec.get("pattern", pattern_spec.get("regex"))
        elif isinstance(pattern_spec, str) and pattern_spec in BUILTIN_FORBIDDEN_PATTERNS:
            pattern = BUILTIN_FORBIDDEN_PATTERNS[pattern_spec]
        if not isinstance(pattern, str):
            continue
        try:
            compiled.append(re.compile(pattern))
        except re.error:
            continue
    return compiled


def _looks_privacy_preserved_value(value: str) -> bool:
    stripped = value.strip().lower()
    if stripped in {"<redacted>", "[redacted]", "redacted", "***redacted***", "<omitted>", "omitted"}:
        return True
    return bool(re.fullmatch(r"(sha256:[a-fA-F0-9]{64}|hash:[A-Za-z0-9._:-]{8,}|tok_[A-Za-z0-9._:-]{4,}|tokenized:[A-Za-z0-9._:-]{4,})", value))


def _field_or_event_declares_safe_transformation(event: dict[str, Any], field_name: str) -> bool:
    safe = {"redacted", "hashed", "tokenized", "bucketed", "omitted"}
    for key in (f"{field_name}_transformation", f"{field_name}_privacy_transformation"):
        value, _ = _lookup_field(event, key)
        if isinstance(value, str) and value in safe:
            return True
    return bool(_event_transformations(event).intersection(safe))


def _safe_lookup(event: dict[str, Any], field_name: str) -> Any:
    value, _ = _lookup_field(event, field_name)
    return None if value is _MISSING else value


def _hyper_message(prop: dict[str, Any], problem: str) -> str:
    label = prop.get("id") if isinstance(prop.get("id"), str) else "hyperproperty"
    return f"{label}: {problem}"


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


def _validate_temporal_property_safety(prop: dict[str, Any], events: list[dict[str, Any]], path: str) -> list[Finding]:
    selector = prop.get("match")
    condition = prop.get("condition")
    if not isinstance(selector, dict) or not isinstance(condition, dict):
        return []
    findings: list[Finding] = []
    for event in events:
        if _event_matches_temporal_selector(event, selector, apply_predicate=False) and not _temporal_predicate_matches(event, condition):
            findings.append(
                Finding(
                    "error",
                    "telemetry.temporal_safety",
                    _temporal_property_message(prop, f"safety condition failed for {event.get('kind')} {event.get('name')!r}"),
                    _temporal_predicate_path(event, condition),
                    f"{path}.condition",
                    _event_index(event),
                    {"property": prop.get("id"), "event": _event_index(event)},
                )
            )
    return findings


def _validate_temporal_property_absence(prop: dict[str, Any], events: list[dict[str, Any]], path: str) -> list[Finding]:
    selector = prop.get("forbidden")
    if not isinstance(selector, dict):
        return []
    findings: list[Finding] = []
    for event in events:
        if _event_matches_temporal_selector(event, selector):
            findings.append(
                Finding(
                    "error",
                    "telemetry.temporal_absence",
                    _temporal_property_message(prop, f"forbidden event {event.get('kind')} {event.get('name')!r} was observed"),
                    f"event[{_event_index(event)}]",
                    f"{path}.forbidden",
                    _event_index(event),
                    {"property": prop.get("id")},
                )
            )
    return findings


def _validate_temporal_property_response(prop: dict[str, Any], events: list[dict[str, Any]], path: str) -> list[Finding]:
    trigger = prop.get("trigger")
    response = prop.get("response")
    within_ms = prop.get("within_ms")
    if not isinstance(trigger, dict) or not isinstance(response, dict) or not isinstance(within_ms, (int, float)) or isinstance(within_ms, bool):
        return []
    findings: list[Finding] = []
    grouped = _groups_for_temporal_property(events, prop.get("group_by", []))
    for group_key, group_events in grouped.items():
        response_events = [event for event in group_events if _event_matches_temporal_selector(event, response)]
        for event in group_events:
            if not _event_matches_temporal_selector(event, trigger):
                continue
            timestamp = _event_timestamp_ms(event)
            witness = _first_event_between(response_events, timestamp, None if timestamp is None else timestamp + float(within_ms))
            if witness is None:
                findings.append(
                    Finding(
                        "error",
                        "telemetry.temporal_response",
                        _temporal_property_message(prop, f"no response {response.get('name')!r} within {within_ms}ms after trigger {trigger.get('name')!r}"),
                        f"event[{_event_index(event)}]",
                        f"{path}.response",
                        _event_index(event),
                        {"property": prop.get("id"), "group": group_key, "within_ms": within_ms},
                    )
                )
    return findings


def _validate_temporal_property_ordering(prop: dict[str, Any], events: list[dict[str, Any]], path: str) -> list[Finding]:
    before = prop.get("before")
    after = prop.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    findings: list[Finding] = []
    allow_equal = prop.get("allow_equal_timestamps", True) is not False
    grouped = _groups_for_temporal_property(events, prop.get("group_by", []))
    for group_key, group_events in grouped.items():
        before_times = [_event_timestamp_ms(event) for event in group_events if _event_matches_temporal_selector(event, before)]
        before_times = [timestamp for timestamp in before_times if timestamp is not None]
        for event in group_events:
            if not _event_matches_temporal_selector(event, after):
                continue
            after_time = _event_timestamp_ms(event)
            if after_time is None:
                continue
            ordered = any(timestamp <= after_time if allow_equal else timestamp < after_time for timestamp in before_times)
            if not ordered:
                findings.append(
                    Finding(
                        "error",
                        "telemetry.temporal_order",
                        _temporal_property_message(prop, f"{after.get('name')!r} occurred without prior {before.get('name')!r}"),
                        f"event[{_event_index(event)}]",
                        f"{path}.before",
                        _event_index(event),
                        {"property": prop.get("id"), "group": group_key},
                    )
                )
    return findings


def _validate_temporal_property_deadline(prop: dict[str, Any], events: list[dict[str, Any]], path: str) -> list[Finding]:
    selector = prop.get("match")
    within_ms = prop.get("within_ms")
    if not isinstance(selector, dict) or not isinstance(within_ms, (int, float)) or isinstance(within_ms, bool):
        return []
    findings: list[Finding] = []
    start = prop.get("start")
    grouped = _groups_for_temporal_property(events, prop.get("group_by", []))
    for group_key, group_events in grouped.items():
        group_times = [_event_timestamp_ms(event) for event in group_events]
        group_times = [timestamp for timestamp in group_times if timestamp is not None]
        start_times = (
            [_event_timestamp_ms(event) for event in group_events if isinstance(start, dict) and _event_matches_temporal_selector(event, start)]
            if isinstance(start, dict)
            else group_times
        )
        start_times = [timestamp for timestamp in start_times if timestamp is not None]
        if not start_times:
            continue
        base = min(start_times)
        for event in group_events:
            if not _event_matches_temporal_selector(event, selector):
                continue
            timestamp = _event_timestamp_ms(event)
            if timestamp is not None and timestamp - base > float(within_ms):
                findings.append(
                    Finding(
                        "error",
                        "telemetry.temporal_deadline",
                        _temporal_property_message(prop, f"{selector.get('name')!r} missed {within_ms}ms deadline by {timestamp - base - float(within_ms):.3f}ms"),
                        f"event[{_event_index(event)}]",
                        f"{path}.within_ms",
                        _event_index(event),
                        {"property": prop.get("id"), "group": group_key, "elapsed_ms": timestamp - base},
                    )
                )
    return findings


def _groups_for_temporal_property(events: list[dict[str, Any]], group_by: Any) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    keys = group_by if isinstance(group_by, list) and all(isinstance(item, str) for item in group_by) else []
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if not keys:
            groups[("__all__",)].append(event)
            continue
        values: list[Any] = []
        for key in keys:
            value, _ = _lookup_field(event, key)
            values.append(value if value is not _MISSING else f"__missing__:{key}:event[{_event_index(event)}]")
        groups[tuple(values)].append(event)
    return groups


def _event_matches_temporal_selector(event: dict[str, Any], selector: dict[str, Any], *, apply_predicate: bool = True) -> bool:
    if event.get("kind") != _normalize_signal_kind(selector.get("kind", selector.get("signal"))):
        return False
    if event.get("name") != selector.get("name"):
        return False
    return not apply_predicate or _temporal_predicate_matches(event, selector, default=True)


def _temporal_predicate_matches(event: dict[str, Any], predicate: dict[str, Any], *, default: bool = False) -> bool:
    field = predicate.get("field")
    if not isinstance(field, str) or not field:
        return default
    value, _ = _lookup_field(event, field)
    is_present = value is not _MISSING
    if "present" in predicate and predicate["present"] is not is_present:
        return False
    if "equals" in predicate and (not is_present or value != predicate["equals"]):
        return False
    if "not_equals" in predicate and (not is_present or value == predicate["not_equals"]):
        return False
    allowed_values = predicate.get("allowed_values")
    if isinstance(allowed_values, list) and (not is_present or value not in allowed_values):
        return False
    if "min" in predicate and (not isinstance(value, (int, float)) or isinstance(value, bool) or value < predicate["min"]):
        return False
    if "max" in predicate and (not isinstance(value, (int, float)) or isinstance(value, bool) or value > predicate["max"]):
        return False
    if "pattern" in predicate:
        if not isinstance(value, str) or re.search(str(predicate["pattern"]), value) is None:
            return False
    return is_present if not any(key in predicate for key in ("present", "equals", "not_equals", "allowed_values", "min", "max", "pattern")) else True


def _temporal_predicate_path(event: dict[str, Any], predicate: dict[str, Any]) -> str:
    field = predicate.get("field")
    if isinstance(field, str) and field:
        _, path = _lookup_field(event, field)
        return path
    return f"event[{_event_index(event)}]"


def _first_event_between(events: list[dict[str, Any]], start_ms: float | None, end_ms: float | None) -> dict[str, Any] | None:
    if start_ms is None or end_ms is None:
        return None
    candidates = [
        (event, timestamp)
        for event in events
        for timestamp in [_event_timestamp_ms(event)]
        if timestamp is not None and start_ms <= timestamp <= end_ms
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[1])[0]


def _temporal_property_message(prop: dict[str, Any], problem: str) -> str:
    label = prop.get("id") if isinstance(prop.get("id"), str) else "temporal property"
    return f"{label}: {problem}"


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


def _validate_field_spec(field_name: str, spec: dict[str, Any], path: str, contract: dict[str, Any] | None = None) -> list[Finding]:
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
    unit = spec.get("unit")
    if unit is not None and (not isinstance(unit, str) or unit not in UNIT_KINDS):
        findings.append(Finding("error", "contract.unit", f"field '{field_name}' has unsupported unit {unit!r}", f"{path}.unit"))
    transformation = spec.get("transformation")
    if transformation is not None and transformation not in ALLOWED_PRIVACY_TRANSFORMATIONS:
        findings.append(Finding("error", "contract.privacy_policy", f"field '{field_name}' has unsupported transformation {transformation!r}", f"{path}.transformation"))
    classification = _privacy_classification(spec)
    policies = (contract or {}).get("privacy_classifications")
    if isinstance(policies, dict) and classification and classification not in PRIVACY_PUBLIC_CLASSES:
        if classification not in policies:
            findings.append(Finding("error", "contract.privacy_policy", f"field '{field_name}' references unknown privacy classification '{classification}'", f"{path}.classification"))
        else:
            allowed = policies[classification].get("allowed_transformations") if isinstance(policies[classification], dict) else None
            if isinstance(allowed, list):
                if transformation is None:
                    findings.append(Finding("error", "contract.privacy_policy", f"field '{field_name}' classification '{classification}' must declare one of {allowed!r}", f"{path}.transformation"))
                elif transformation not in allowed:
                    findings.append(Finding("error", "contract.privacy_policy", f"field '{field_name}' transformation {transformation!r} is not allowed for classification '{classification}'", f"{path}.transformation"))
    return findings


def _validate_regex(pattern: str, path: str, message: str, *, code: str = "contract.invalid_regex") -> list[Finding]:
    try:
        re.compile(pattern)
    except re.error as exc:
        return [Finding("error", code, f"{message}: {exc}", path)]
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
                if field_spec.get("required", True) and field_spec.get("transformation") != "omitted":
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
    findings.extend(_validate_privacy_transformation(field_name, spec, value, event, contract_path, event_path))
    findings.extend(_validate_sensitive_value(field_name, spec, value, event, contract_path, event_path))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "min" in spec and value < spec["min"]:
            findings.append(Finding("error", "telemetry.numeric_min", f"field '{field_name}' value {value} is below minimum {spec['min']}", event_path, contract_path, _event_index(event)))
        if "max" in spec and value > spec["max"]:
            findings.append(Finding("error", "telemetry.numeric_max", f"field '{field_name}' value {value} is above maximum {spec['max']}", event_path, contract_path, _event_index(event)))
    findings.extend(_validate_unit(field_name, spec, value, event, contract_path, event_path))
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


def _privacy_classification(spec: dict[str, Any]) -> str:
    return str(spec.get("privacy_classification") or spec.get("classification") or spec.get("sensitivity") or "").lower()


def _validate_privacy_transformation(field_name: str, spec: dict[str, Any], value: Any, event: dict[str, Any], contract_path: str, event_path: str) -> list[Finding]:
    transformation = spec.get("transformation")
    if transformation is None or transformation == "raw":
        return []
    message = ""
    if transformation == "redacted":
        if not isinstance(value, str) or value.strip().lower() not in {"<redacted>", "[redacted]", "redacted", "***redacted***"}:
            message = f"field '{field_name}' must be emitted as a redacted sentinel"
    elif transformation == "hashed":
        if not isinstance(value, str) or re.fullmatch(r"(sha256:[a-fA-F0-9]{64}|hash:[A-Za-z0-9._:-]{8,})", value) is None:
            message = f"field '{field_name}' must be emitted as a stable hash token"
    elif transformation == "tokenized":
        if not isinstance(value, str) or not (value.startswith("tok_") or value.startswith("tokenized:")):
            message = f"field '{field_name}' must be emitted as a tokenized surrogate"
    elif transformation == "bucketed":
        if isinstance(value, str) and RAW_SECRET_VALUE.search(value):
            message = f"field '{field_name}' bucketed value still appears to contain raw sensitive data"
    elif transformation == "omitted":
        if not (value is None or value == "" or value == "<omitted>"):
            message = f"field '{field_name}' must be omitted, not emitted with a raw value"
    if not message:
        return []
    return [
        Finding(
            "error",
            "telemetry.privacy_transformation",
            message,
            event_path,
            contract_path,
            _event_index(event),
            {"transformation": transformation, "value_preview": _preview(value) if isinstance(value, str) else None},
        )
    ]


def _validate_unit(field_name: str, spec: dict[str, Any], value: Any, event: dict[str, Any], contract_path: str, event_path: str) -> list[Finding]:
    unit = spec.get("unit")
    if not isinstance(unit, str) or unit not in UNIT_KINDS:
        return []
    kind = UNIT_KINDS[unit]
    valid = True
    expectation = ""
    if kind == "duration":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
        expectation = "a non-negative numeric duration"
    elif kind == "bytes":
        valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        expectation = "a non-negative integer byte-size value"
    elif kind == "percent":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 100
        expectation = "a numeric percentage from 0 through 100"
    elif kind == "ratio":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
        expectation = "a numeric ratio from 0 through 1"
    elif kind == "count":
        valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
        expectation = "a non-negative integer count"
    elif kind == "timestamp":
        valid = _unit_timestamp_valid(value)
        expectation = "a positive numeric timestamp or ISO-8601 timestamp string"
    elif kind == "currency":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
        expectation = "a non-negative numeric currency amount"
    if valid:
        return []
    return [Finding("error", "telemetry.unit", f"field '{field_name}' with unit {unit!r} must be {expectation}", event_path, contract_path, _event_index(event), {"unit": unit, "value": value})]


def _unit_timestamp_valid(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value > 0
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


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
