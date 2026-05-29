from pathlib import Path
import json

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.schema import CONTRACT_SCHEMA
from telemetry_contracts.validator import validate_contract_shape, validate_events

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "examples/contracts/checkout.contract.json"


def codes(findings):
    return {finding.code for finding in findings}


def test_passing_example_has_no_findings():
    findings = validate_events(load_contract(CONTRACT), load_jsonl(ROOT / "examples/telemetry/passing.jsonl"))
    assert findings == []


def test_failing_example_reports_useful_errors():
    findings = validate_events(load_contract(CONTRACT), load_jsonl(ROOT / "examples/telemetry/failing.jsonl"))
    assert "telemetry.pattern" in codes(findings)
    assert "telemetry.allowed_values" in codes(findings)
    assert "telemetry.numeric_min" in codes(findings)
    assert "telemetry.missing_signal" in codes(findings)  # latency metric is absent
    assert any(item.severity == "error" for item in findings)


def test_cardinality_hint_is_warning_not_error():
    contract = {
        "version": "1.0",
        "service": "svc",
        "metrics": [{"name": "m", "tags": {"user": {"type": "string", "cardinality": {"max": 1}}}}],
    }
    events = [
        {"kind": "metric", "service": "svc", "name": "m", "value": 1, "tags": {"user": "a"}},
        {"kind": "metric", "service": "svc", "name": "m", "value": 1, "tags": {"user": "b"}},
    ]
    findings = validate_events(contract, events)
    assert [(item.severity, item.code) for item in findings] == [("warning", "telemetry.cardinality")]


def test_sensitive_schema_and_forbidden_patterns_are_enforced():
    contract = {
        "version": "1.0",
        "service": "svc",
        "logs": [
            {
                "name": "auth.failure",
                "fields": {
                    "auth_token": {
                        "type": "string",
                        "sensitivity": "token",
                        "forbidden_patterns": ["bearer_token"],
                    },
                    "user_email": {
                        "type": "string",
                        "sensitivity": "pii",
                        "forbidden_patterns": ["email"],
                    },
                    "session_id": {"type": "string"},
                },
            }
        ],
    }
    events = [
        {
            "kind": "log",
            "service": "svc",
            "name": "auth.failure",
            "fields": {
                "auth_token": "Bearer abcdefghijklmnop",
                "user_email": "person@example.com",
                "session_id": "session-123",
            },
        }
    ]
    findings = validate_events(contract, events)
    assert "telemetry.forbidden_pattern" in codes(findings)
    assert "telemetry.sensitive_value" in codes(findings)
    assert "telemetry.sensitive_unclassified" in codes(findings)
    assert any(item.to_dict()["category"] == "privacy-security" for item in findings)


def test_contract_lint_reports_schema_semantic_errors():
    findings = validate_contract_shape(
        {
            "version": "1.0",
            "service": "svc",
            "metrics": [
                {
                    "name": "latency",
                    "required": "yes",
                    "value": {"type": "duration", "min": 10, "max": 1},
                    "tags": {
                        "auth_token": {
                            "type": "string",
                            "required": "true",
                            "allowed_values": "acme",
                            "pattern": "[",
                            "forbidden_patterns": [{"name": "bad"}],
                        }
                    },
                    "conditional_requirements": [{"if": {"present": "yes"}, "then": {"fields": []}}],
                }
            ],
            "logs": [
                {"name": "failed", "severity_policy": {"min": "LOUD"}}
            ],
        }
    )
    finding_codes = codes(findings)
    assert "contract.required_type" in finding_codes
    assert "contract.field_type" in finding_codes
    assert "contract.numeric_bounds" in finding_codes
    assert "contract.allowed_values_type" in finding_codes
    assert "contract.invalid_regex" in finding_codes
    assert "contract.forbidden_patterns_type" in finding_codes
    assert "contract.sensitive_field_unclassified" in finding_codes
    assert "contract.conditional_requirement" in finding_codes
    assert "contract.severity_policy" in finding_codes


def test_published_contract_schema_matches_runtime_schema():
    published = json.loads((ROOT / "docs/contract.schema.json").read_text(encoding="utf-8"))
    assert published == CONTRACT_SCHEMA


def test_contract_schema_validation_rejects_bad_shapes():
    findings = validate_contract_shape(
        {
            "version": "1.0",
            "service": "svc",
            "spans": [{"name": "request", "required": "yes"}],
            "correlation": {"keys": "trace_id"},
        }
    )
    finding_codes = codes(findings)
    assert "contract.schema" in finding_codes
    assert "contract.required_type" in finding_codes


def test_correlation_policy_requires_shared_keys_across_signals():
    contract = {
        "version": "1.0",
        "service": "svc",
        "correlation": {"keys": ["trace_id", "request_id"], "require_on": ["spans", "logs"]},
        "spans": [{"name": "request"}],
        "logs": [{"name": "failed"}],
    }
    missing = validate_events(
        contract,
        [
            {"kind": "span", "service": "svc", "name": "request", "trace_id": "trace-a"},
            {"kind": "log", "service": "svc", "name": "failed", "fields": {"request_id": "request-b"}},
        ],
    )
    assert "telemetry.correlation_mismatch" in codes(missing)

    passing = validate_events(
        contract,
        [
            {"kind": "span", "service": "svc", "name": "request", "trace_id": "trace-a"},
            {"kind": "log", "service": "svc", "name": "failed", "fields": {"trace_id": "trace-a"}},
        ],
    )
    assert passing == []


def test_conditional_requirements_enforce_dependent_fields():
    contract = {
        "version": "1.0",
        "service": "svc",
        "spans": [
            {
                "name": "payment.authorize",
                "fields": {"error_code": {"type": "string", "required": False}},
                "conditional_requirements": [
                    {"if": {"field": "error_code", "present": True}, "then": {"fields": ["remediation_hint", "retryable"]}}
                ],
            }
        ],
    }
    findings = validate_events(
        contract,
        [{"kind": "span", "service": "svc", "name": "payment.authorize", "fields": {"error_code": "TIMEOUT", "retryable": True}}],
    )
    assert "telemetry.conditional_missing_field" in codes(findings)

    passing = validate_events(
        contract,
        [
            {
                "kind": "span",
                "service": "svc",
                "name": "payment.authorize",
                "fields": {"error_code": "TIMEOUT", "retryable": True, "remediation_hint": "retry provider"},
            }
        ],
    )
    assert passing == []


def test_log_severity_policy_supports_minimum_thresholds():
    contract = {
        "version": "1.0",
        "service": "svc",
        "logs": [{"name": "checkout.failed", "severity_policy": {"min": "WARN"}}],
    }
    findings = validate_events(contract, [{"kind": "log", "service": "svc", "name": "checkout.failed", "severity": "INFO"}])
    assert "telemetry.log_severity_min" in codes(findings)
    assert validate_events(contract, [{"kind": "log", "service": "svc", "name": "checkout.failed", "severity": "ERROR"}]) == []


def test_lint_reports_duplicate_signals_and_fields():
    findings = validate_contract_shape(
        {
            "version": "1.0",
            "service": "svc",
            "logs": [
                {"name": "checkout.failed", "fields": {"tenant_id": {"type": "string"}}, "attributes": {"tenant_id": {"type": "string"}}},
                {"name": "checkout.failed"},
            ],
        }
    )
    finding_codes = codes(findings)
    assert "contract.duplicate_signal" in finding_codes
    assert "contract.duplicate_field" in finding_codes



def test_reusable_field_definitions_are_resolved_and_linted():
    contract = {
        "version": "1.0",
        "service": "svc",
        "field_definitions": {
            "tenant_id": {"type": "string", "pattern": "tenant-[a-z]+", "required": True},
            "bounded_count": {"type": "integer", "min": 0, "max": 3},
        },
        "spans": [
            {
                "name": "request",
                "fields": {
                    "tenant_id": {"$ref": "#/field_definitions/tenant_id"},
                    "retry_count": {"ref": "bounded_count", "max": 2},
                },
            }
        ],
        "metrics": [{"name": "attempts", "value": {"ref": "bounded_count"}}],
    }

    passing = [
        {"kind": "span", "service": "svc", "name": "request", "fields": {"tenant_id": "tenant-acme", "retry_count": 2}},
        {"kind": "metric", "service": "svc", "name": "attempts", "value": 1},
    ]
    assert validate_contract_shape(contract) == []
    assert validate_events(contract, passing) == []

    failing = [
        {"kind": "span", "service": "svc", "name": "request", "fields": {"tenant_id": "acme", "retry_count": 3}},
        {"kind": "metric", "service": "svc", "name": "attempts", "value": -1},
    ]
    finding_codes = codes(validate_events(contract, failing))
    assert "telemetry.pattern" in finding_codes
    assert "telemetry.numeric_max" in finding_codes
    assert "telemetry.numeric_min" in finding_codes

    bad_contract = {"version": "1.0", "service": "svc", "spans": [{"name": "request", "fields": {"tenant_id": {"ref": "missing"}}}]}
    assert "contract.field_ref" in codes(validate_contract_shape(bad_contract))


def test_temporal_sequences_require_ordered_steps_within_window():
    contract = {
        "version": "1.0",
        "service": "svc",
        "temporal_sequences": [
            {
                "id": "request-to-error",
                "group_by": ["trace_id"],
                "window_ms": 500,
                "steps": [
                    {"kind": "span", "name": "request"},
                    {"kind": "metric", "name": "request.count"},
                    {"kind": "log", "name": "request.failed"},
                ],
            }
        ],
        "spans": [{"name": "request"}],
        "metrics": [{"name": "request.count"}],
        "logs": [{"name": "request.failed"}],
    }

    passing = [
        {"kind": "span", "service": "svc", "name": "request", "trace_id": "a", "timestamp_ms": 1000},
        {"kind": "metric", "service": "svc", "name": "request.count", "trace_id": "a", "timestamp_ms": 1100, "value": 1},
        {"kind": "log", "service": "svc", "name": "request.failed", "trace_id": "a", "timestamp_ms": 1200},
    ]
    assert validate_events(contract, passing) == []

    out_of_order = [
        {"kind": "span", "service": "svc", "name": "request", "trace_id": "a", "timestamp_ms": 1000},
        {"kind": "log", "service": "svc", "name": "request.failed", "trace_id": "a", "timestamp_ms": 1050},
        {"kind": "metric", "service": "svc", "name": "request.count", "trace_id": "a", "timestamp_ms": 1100, "value": 1},
    ]
    assert "telemetry.temporal_order" in codes(validate_events(contract, out_of_order))

    too_slow = [
        {"kind": "span", "service": "svc", "name": "request", "trace_id": "a", "timestamp_ms": 1000},
        {"kind": "metric", "service": "svc", "name": "request.count", "trace_id": "a", "timestamp_ms": 1100, "value": 1},
        {"kind": "log", "service": "svc", "name": "request.failed", "trace_id": "a", "timestamp_ms": 2000},
    ]
    assert "telemetry.temporal_window" in codes(validate_events(contract, too_slow))

    missing_step = [
        {"kind": "span", "service": "svc", "name": "request", "trace_id": "a", "timestamp_ms": 1000},
        {"kind": "metric", "service": "svc", "name": "request.count", "trace_id": "a", "timestamp_ms": 1100, "value": 1},
    ]
    assert "telemetry.temporal_missing_step" in codes(validate_events(contract, missing_step))
