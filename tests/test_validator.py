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


def test_strict_validation_reports_closed_world_drift():
    contract = {
        "version": "1.0",
        "service": "checkout",
        "spans": [{"name": "checkout.request", "attributes": {"tenant_id": {"type": "string"}}}],
    }
    events = [
        {"kind": "span", "service": "checkout", "name": "checkout.request", "attributes": {"tenant_id": "tenant-a", "debug_user": "42"}},
        {"kind": "log", "service": "checkout", "name": "checkout.debug", "fields": {"tenant_id": "tenant-a"}},
        {"kind": "span", "service": "payments", "name": "payment.request"},
        {"kind": "span", "service": "checkout", "name": "checkout.request", "transformations": ["tail_sampling"]},
    ]

    default_findings = validate_events(contract, events)
    assert not any(finding.code.startswith("telemetry.strict_") for finding in default_findings)

    strict_findings = validate_events(contract, events, strict=True)
    assert "telemetry.strict_unexpected_field" in codes(strict_findings)
    assert "telemetry.strict_undeclared_signal" in codes(strict_findings)
    assert "telemetry.strict_unmodeled_service" in codes(strict_findings)
    assert "telemetry.strict_undocumented_transformation" in codes(strict_findings)


def test_strict_validation_escape_hatches_are_precise():
    contract = {
        "version": "1.0",
        "service": "checkout",
        "metadata": {
            "strict_validation": {
                "enabled": True,
                "allow_unmodeled_services": ["collector"],
                "allow_undeclared_signals": [{"kind": "log", "name": "checkout.debug"}],
                "allowed_extra_fields": [{"kind": "span", "name": "checkout.request", "fields": ["debug_user"]}],
                "allow_collector_transformations": ["tail_sampling"],
            }
        },
        "spans": [{"name": "checkout.request", "attributes": {"tenant_id": {"type": "string"}}}],
    }
    events = [
        {"kind": "span", "service": "checkout", "name": "checkout.request", "attributes": {"tenant_id": "tenant-a", "debug_user": "42"}, "transformations": ["tail_sampling"]},
        {"kind": "log", "service": "checkout", "name": "checkout.debug", "fields": {"tenant_id": "tenant-a"}},
        {"kind": "span", "service": "collector", "name": "collector.flush"},
    ]

    assert validate_events(contract, events) == []


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


def test_phone_detection_does_not_treat_dates_as_pii():
    contract = {
        "version": "1.0",
        "service": "svc",
        "logs": [
            {
                "name": "job.finished",
                "fields": {
                    "completed_on": {"type": "string"},
                    "phone": {"type": "string", "sensitivity": "pii", "forbidden_patterns": ["phone"]},
                },
            }
        ],
    }
    findings = validate_events(
        contract,
        [
            {
                "kind": "log",
                "service": "svc",
                "name": "job.finished",
                "fields": {"completed_on": "2026-05-29", "phone": "+1 415 555 0199"},
            }
        ],
    )

    assert all(item.path != "event[1].completed_on" for item in findings)
    assert "telemetry.forbidden_pattern" in codes(findings)
    assert "telemetry.sensitive_value" in codes(findings)


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


def test_hyperproperty_lint_reports_bad_shapes():
    findings = validate_contract_shape(
        {
            "version": "1.0",
            "service": "svc",
            "hyperproperties": [
                {"type": "pii_non_disclosure", "sensitive_fields": []},
                {"type": "tenant_non_interference", "isolation_keys": []},
                {"type": "unknown"},
            ],
        }
    )
    assert "contract.hyperproperty" in codes(findings)


def test_published_contract_schema_matches_runtime_schema():
    published = json.loads((ROOT / "docs/contract.schema.json").read_text(encoding="utf-8"))
    assert published == CONTRACT_SCHEMA


def test_hyperproperties_find_pii_disclosure_and_tenant_interference():
    contract = load_contract(ROOT / "examples/hyperproperties/contract.json")
    findings = validate_events(contract, load_jsonl(ROOT / "examples/hyperproperties/failing.jsonl"))
    finding_codes = codes(findings)

    assert "telemetry.hyper_pii_disclosure" in finding_codes
    assert "telemetry.hyper_tenant_interference" in finding_codes
    tenant_finding = next(item for item in findings if item.code == "telemetry.hyper_tenant_interference")
    assert tenant_finding.details["shared_key"] == "trace_id"
    assert tenant_finding.details["left_tenant"] == "tenant-a"
    assert tenant_finding.details["right_tenant"] == "tenant-b"


def test_hyperproperties_accept_transformed_sensitive_values_and_isolated_tenants():
    contract = load_contract(ROOT / "examples/hyperproperties/contract.json")
    findings = validate_events(contract, load_jsonl(ROOT / "examples/hyperproperties/passing.jsonl"))

    assert findings == []


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


def test_sampling_retention_policy_stubs_are_machine_readable():
    good = {
        "version": "1.0",
        "service": "svc",
        "metadata": {
            "sampling": {
                "traces": {"strategy": "parent_based", "minimum_rate": 0.25, "always_sample_errors": True},
                "logs": {"strategy": "always_on", "minimum_rate": 1.0},
            },
            "retention": {"traces_days": 7, "metrics_days": 30, "logs_days": 14},
        },
    }
    assert validate_contract_shape(good) == []

    bad = {
        "version": "1.0",
        "service": "svc",
        "metadata": {
            "sampling": {"traces": {"strategy": "coin_flip", "minimum_rate": 2, "always_sample_errors": "yes"}},
            "retention": {"logs_days": 0, "debug_days": 3},
        },
    }
    assert "contract.policy_stub" in codes(validate_contract_shape(bad))


def test_privacy_classifications_require_allowed_transformations():
    contract = {
        "version": "1.0",
        "service": "svc",
        "privacy_classifications": {"token": {"allowed_transformations": ["redacted", "hashed", "omitted"]}},
        "logs": [
            {
                "name": "auth",
                "fields": {
                    "auth_token": {
                        "type": "string",
                        "classification": "token",
                        "transformation": "hashed",
                    }
                },
            }
        ],
    }
    assert validate_contract_shape(contract) == []
    findings = validate_events(contract, [{"kind": "log", "service": "svc", "name": "auth", "fields": {"auth_token": "Bearer raw-secret-token"}}])
    assert "telemetry.privacy_transformation" in codes(findings)
    assert validate_events(
        contract,
        [{"kind": "log", "service": "svc", "name": "auth", "fields": {"auth_token": "sha256:" + "a" * 64}}],
    ) == []

    missing_transform = {
        "version": "1.0",
        "service": "svc",
        "privacy_classifications": {"token": {"allowed_transformations": ["redacted"]}},
        "logs": [{"name": "auth", "fields": {"auth_token": {"type": "string", "classification": "token"}}}],
    }
    assert "contract.privacy_policy" in codes(validate_contract_shape(missing_transform))


def test_units_are_linted_and_validated():
    contract = {
        "version": "1.0",
        "service": "svc",
        "metrics": [
            {"name": "latency", "value": {"type": "number", "unit": "ms"}},
            {"name": "success_ratio", "value": {"type": "number", "unit": "ratio"}},
        ],
        "spans": [{"name": "request", "fields": {"attempts": {"type": "integer", "unit": "count"}}}],
    }
    assert validate_contract_shape(contract) == []
    findings = validate_events(
        contract,
        [
            {"kind": "metric", "service": "svc", "name": "latency", "value": -1},
            {"kind": "metric", "service": "svc", "name": "success_ratio", "value": 1.5},
            {"kind": "span", "service": "svc", "name": "request", "fields": {"attempts": 1.2}},
        ],
    )
    assert "telemetry.unit" in codes(findings)

    bad_contract = {"version": "1.0", "service": "svc", "metrics": [{"name": "m", "value": {"type": "number", "unit": "parsecs"}}]}
    assert "contract.unit" in codes(validate_contract_shape(bad_contract))


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


def test_temporal_logic_properties_cover_safety_response_absence_ordering_and_deadline():
    contract = load_contract(ROOT / "examples/temporal_logic/contract.json")
    assert validate_contract_shape(contract) == []
    assert validate_events(contract, load_jsonl(ROOT / "examples/temporal_logic/passing.jsonl")) == []

    findings = validate_events(contract, load_jsonl(ROOT / "examples/temporal_logic/failing.jsonl"))
    finding_codes = codes(findings)
    assert "telemetry.temporal_safety" in finding_codes
    assert "telemetry.temporal_response" in finding_codes
    assert "telemetry.temporal_absence" in finding_codes
    assert "telemetry.temporal_order" in finding_codes
    assert "telemetry.temporal_deadline" in finding_codes


def test_gitlab_temporal_property_finds_missing_backup_alert_response():
    contract = load_contract(ROOT / "case_studies/gitlab_2017_database_outage/contract.json")
    findings = validate_events(contract, load_jsonl(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl"))
    assert "telemetry.temporal_response" in codes(findings)


def test_runtime_sensitive_checks_cover_credentials_pii_tenant_and_payload_preview():
    contract = load_contract(ROOT / "examples/benchmarks/unsafe_transformations.contract.json")
    events = load_jsonl(ROOT / "examples/benchmarks/unsafe_transformations.events.jsonl")
    findings = validate_events(contract, events)
    risk_kinds = {item.details.get("risk_kind") for item in findings if item.code == "telemetry.sensitive_value"}
    assert {"credential_or_token", "email", "phone", "raw_payload_preview"} <= risk_kinds
    assert any(item.code == "telemetry.privacy_transformation" and item.contract_path.endswith("tenant_id") for item in findings)
