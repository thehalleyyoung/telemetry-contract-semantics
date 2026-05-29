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
