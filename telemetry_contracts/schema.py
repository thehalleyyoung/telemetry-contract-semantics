from __future__ import annotations

from typing import Any

from .findings import Finding

CONTRACT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.org/telemetry-contracts/contract.schema.json",
    "title": "Telemetry Contracts contract",
    "type": "object",
    "required": ["version", "service"],
    "properties": {
        "version": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
        "service": {"type": "string"},
        "metadata": {"$ref": "#/$defs/metadata"},
        "privacy_classifications": {"type": "object", "additionalProperties": {"$ref": "#/$defs/privacyClassification"}},
        "field_definitions": {"type": "object", "additionalProperties": {"$ref": "#/$defs/fieldSpec"}},
        "spans": {"type": "array", "items": {"$ref": "#/$defs/spanSignal"}},
        "metrics": {"type": "array", "items": {"$ref": "#/$defs/metricSignal"}},
        "logs": {"type": "array", "items": {"$ref": "#/$defs/logSignal"}},
        "correlation": {"$ref": "#/$defs/correlationPolicy"},
        "temporal_sequences": {"type": "array", "items": {"$ref": "#/$defs/temporalSequence"}},
        "static_expectations": {"$ref": "#/$defs/staticExpectations"},
        "static_rules": {"type": "object"},
        "scenarios": {"type": "array", "items": {"$ref": "#/$defs/scenario"}},
        "alternative_obligations": {"type": "array", "items": {"$ref": "#/$defs/alternativeObligation"}},
    },
    "$defs": {
        "primitive": {"enum": ["string", "integer", "number", "boolean", "object", "array", "null", "str", "int", "float", "bool", "dict", "list"]},
        "fieldSpec": {
            "anyOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "properties": {
                        "$ref": {"type": "string"},
                        "ref": {"type": "string"},
                        "type": {"$ref": "#/$defs/primitive"},
                        "required": {"type": "boolean"},
                        "allowed_values": {"type": "array"},
                        "pattern": {"type": "string"},
                        "regex": {"type": "string"},
                        "min": {"type": "number"},
                        "max": {"type": "number"},
                        "cardinality": {"$ref": "#/$defs/cardinality"},
                        "sensitivity": {"type": "string"},
                        "classification": {"type": "string"},
                        "privacy_classification": {"type": "string"},
                        "transformation": {"enum": ["raw", "redacted", "hashed", "tokenized", "bucketed", "omitted"]},
                        "unit": {"type": "string"},
                        "pii": {"type": "boolean"},
                        "allow_raw_sensitive": {"type": "boolean"},
                        "forbidden_patterns": {
                            "anyOf": [
                                {"type": "string"},
                                {"$ref": "#/$defs/forbiddenPattern"},
                                {"type": "array", "items": {"anyOf": [{"type": "string"}, {"$ref": "#/$defs/forbiddenPattern"}]}}
                            ]
                        },
                    },
                },
            ]
        },
        "fieldMap": {"type": "object", "additionalProperties": {"$ref": "#/$defs/fieldSpec"}},
        "metadata": {
            "type": "object",
            "properties": {
                "owner": {"type": "string"},
                "sampling": {"type": "object", "additionalProperties": {"$ref": "#/$defs/samplingPolicy"}},
                "retention": {"type": "object", "additionalProperties": {"type": "integer"}},
                "transformation_preservation": {
                    "type": "object",
                    "properties": {
                        "approved_transformations": {"type": "array", "items": {"type": "string"}},
                        "preserve_scenarios": {"type": "array", "items": {"type": "string"}},
                        "claim": {"type": "string"},
                    },
                },
                "strict_validation": {"$ref": "#/$defs/strictValidationPolicy"},
            },
        },
        "strictValidationPolicy": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "allow_all_extra_fields": {"type": "boolean"},
                "allow_unmodeled_services": {"type": "array", "items": {"type": "string"}},
                "allow_collector_transformations": {"type": "array", "items": {"type": "string"}},
                "allow_undeclared_signals": {"type": "array", "items": {"$ref": "#/$defs/strictSignalEscape"}},
                "allow_unexpected_fields": {"type": "array", "items": {"$ref": "#/$defs/strictFieldEscape"}},
                "allowed_extra_fields": {"type": "array", "items": {"$ref": "#/$defs/strictFieldEscape"}},
            },
        },
        "strictSignalEscape": {
            "anyOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "properties": {
                        "kind": {"enum": ["span", "log", "metric", "spans", "logs", "metrics"]},
                        "signal": {"enum": ["span", "log", "metric", "spans", "logs", "metrics"]},
                        "name": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
            ],
        },
        "strictFieldEscape": {
            "anyOf": [
                {"type": "string"},
                {
                    "type": "object",
                    "properties": {
                        "kind": {"enum": ["span", "log", "metric", "spans", "logs", "metrics"]},
                        "signal": {"enum": ["span", "log", "metric", "spans", "logs", "metrics"]},
                        "name": {"type": "string"},
                        "field": {"type": "string"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "reason": {"type": "string"},
                    },
                },
            ],
        },
        "samplingPolicy": {
            "type": "object",
            "properties": {
                "strategy": {"enum": ["always_on", "always_off", "parent_based", "probabilistic", "tail_based", "rate_limited"]},
                "minimum_rate": {"type": "number"},
                "rate": {"type": "number"},
                "always_sample_errors": {"type": "boolean"},
                "always_keep_errors": {"type": "boolean"},
            },
        },
        "privacyClassification": {
            "type": "object",
            "required": ["allowed_transformations"],
            "properties": {
                "description": {"type": "string"},
                "allowed_transformations": {
                    "type": "array",
                    "items": {"enum": ["raw", "redacted", "hashed", "tokenized", "bucketed", "omitted"]},
                },
            },
        },
        "cardinality": {
            "type": "object",
            "properties": {
                "max": {"type": "integer"},
                "policy": {"type": "string"},
            },
        },
        "forbiddenPattern": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "pattern": {"type": "string"},
                "regex": {"type": "string"},
            },
        },
        "baseSignal": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "required": {"type": "boolean"},
                "fields": {"$ref": "#/$defs/fieldMap"},
                "attributes": {"$ref": "#/$defs/fieldMap"},
                "tags": {"$ref": "#/$defs/fieldMap"},
                "conditional_requirements": {"type": "array", "items": {"$ref": "#/$defs/conditionalRequirement"}},
            },
        },
        "spanSignal": {"allOf": [{"$ref": "#/$defs/baseSignal"}]},
        "metricSignal": {
            "allOf": [
                {"$ref": "#/$defs/baseSignal"},
                {"type": "object", "properties": {"value": {"$ref": "#/$defs/fieldSpec"}}},
            ]
        },
        "logSignal": {
            "allOf": [
                {"$ref": "#/$defs/baseSignal"},
                {"type": "object", "properties": {"severity": {"type": "string"}, "severity_policy": {"$ref": "#/$defs/severityPolicy"}, "message_pattern": {"type": "string"}}},
            ]
        },
        "conditionalRequirement": {
            "type": "object",
            "required": ["if", "then"],
            "properties": {
                "if": {"$ref": "#/$defs/fieldCondition"},
                "then": {"$ref": "#/$defs/conditionalThen"},
            },
        },
        "fieldCondition": {
            "type": "object",
            "required": ["field"],
            "properties": {
                "field": {"type": "string"},
                "present": {"type": "boolean"},
                "equals": {},
                "allowed_values": {"type": "array"},
            },
        },
        "conditionalThen": {
            "type": "object",
            "properties": {
                "fields": {"type": "array", "items": {"type": "string"}},
            },
        },
        "severityPolicy": {
            "type": "object",
            "properties": {
                "min": {"type": "string"},
                "minimum": {"type": "string"},
            },
        },
        "correlationPolicy": {
            "type": "object",
            "required": ["keys"],
            "properties": {
                "keys": {"type": "array", "items": {"type": "string"}},
                "require_on": {"type": "array", "items": {"enum": ["spans", "logs", "metrics", "span", "log", "metric"]}},
            },
        },
        "temporalSequence": {
            "type": "object",
            "required": ["steps"],
            "properties": {
                "id": {"type": "string"},
                "required": {"type": "boolean"},
                "window_ms": {"type": "number"},
                "group_by": {"type": "array", "items": {"type": "string"}},
                "steps": {"type": "array", "items": {"$ref": "#/$defs/temporalStep"}},
            },
        },
        "temporalStep": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "kind": {"enum": ["span", "log", "metric", "spans", "logs", "metrics"]},
                "signal": {"enum": ["span", "log", "metric", "spans", "logs", "metrics"]},
                "name": {"type": "string"},
            },
        },
        "staticExpectations": {
            "type": "object",
            "properties": {
                "spans": {"type": "array", "items": {"type": "string"}},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "logs": {"type": "array", "items": {"type": "string"}},
            },
        },
        "scenario": {
            "type": "object",
            "required": ["id"],
            "anyOf": [
                {"required": ["requires"]},
                {"required": ["minimum_observations"]},
            ],
            "properties": {
                "id": {"type": "string"},
                "question": {"type": "string"},
                "requires": {"type": "array", "items": {"$ref": "#/$defs/scenarioRequirement"}},
                "minimum_observations": {"type": "array", "items": {"$ref": "#/$defs/scenarioRequirement"}},
            },
        },
        "alternativeObligation": {
            "type": "object",
            "required": ["id", "any_of"],
            "properties": {
                "id": {"type": "string"},
                "purpose": {"type": "string"},
                "description": {"type": "string"},
                "required": {"type": "boolean"},
                "any_of": {"type": "array", "items": {"$ref": "#/$defs/alternativeOption"}},
            },
        },
        "alternativeOption": {
            "type": "object",
            "required": ["signal", "name"],
            "properties": {
                "id": {"type": "string"},
                "signal": {"enum": ["span", "log", "metric", "spans", "logs", "metrics"]},
                "kind": {"enum": ["span", "log", "metric", "spans", "logs", "metrics"]},
                "name": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}},
            },
        },
        "scenarioRequirement": {
            "type": "object",
            "anyOf": [
                {"required": ["signal", "name"]},
                {"required": ["any_of"]},
            ],
            "properties": {
                "id": {"type": "string"},
                "signal": {"enum": ["span", "log", "metric"]},
                "name": {"type": "string"},
                "purpose": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}},
                "any_of": {"type": "array", "items": {"$ref": "#/$defs/alternativeOption"}},
            },
        },
    },
}


def validate_contract_schema(contract: Any) -> list[Finding]:
    return [
        Finding("error", "contract.schema", message, path)
        for path, message in _validate_schema(contract, CONTRACT_SCHEMA, "$", CONTRACT_SCHEMA)
    ]


def _validate_schema(value: Any, schema: dict[str, Any], path: str, root: dict[str, Any]) -> list[tuple[str, str]]:
    if "$ref" in schema:
        schema = _resolve_ref(root, schema["$ref"])
    errors: list[tuple[str, str]] = []
    for subschema in schema.get("allOf", []):
        errors.extend(_validate_schema(value, subschema, path, root))
    if "anyOf" in schema:
        if not any(not _validate_schema(value, subschema, path, root) for subschema in schema["anyOf"]):
            errors.append((path, "value does not match any allowed schema"))
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append((path, f"value {value!r} is not one of {schema['enum']!r}"))
        return errors
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_json_type(value, expected_type):
        errors.append((path, f"expected {expected_type}, got {type(value).__name__}"))
        return errors
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append((f"{path}.{key}", "required property is missing"))
        properties = schema.get("properties", {})
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors.extend(_validate_schema(child, properties[key], child_path, root))
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(_validate_schema(child, schema["additionalProperties"], child_path, root))
            elif schema.get("additionalProperties") is False:
                errors.append((child_path, "unexpected property"))
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for index, item in enumerate(value):
            errors.extend(_validate_schema(item, schema["items"], f"{path}[{index}]", root))
    return errors


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported schema ref: {ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _matches_json_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False
