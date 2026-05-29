from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.validator import validate_events

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
