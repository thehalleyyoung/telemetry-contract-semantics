from pathlib import Path

from telemetry_contracts.loader import load_contract
from telemetry_contracts.static_checker import check_sources

ROOT = Path(__file__).resolve().parents[1]


def test_static_checker_finds_example_instrumentation():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    assert check_sources(contract, [ROOT / "examples/services"]) == []


def test_static_checker_reports_missing_name():
    source = ROOT / "tests/fixtures/no_instrumentation.py"
    findings = check_sources({"service": "svc", "spans": [{"name": "important.span"}]}, [source])
    assert findings[0].code == "static.missing_instrumentation"
    assert findings[0].details["obligation"] == {"kind": "span", "name": "important.span"}


def test_static_checker_reports_secret_logging_with_location():
    source = ROOT / "case_studies/current/owasp_securetea_signin/Signin.js"
    findings = check_sources({"service": "securetea", "static_expectations": {"spans": [], "metrics": [], "logs": []}}, [source])
    secret_findings = [item for item in findings if item.code == "static.secret_logging"]
    assert [item.details["source_span"]["line"] for item in secret_findings] == [27, 48]
    assert all(item.path.endswith(":69") or item.path.endswith(":41") for item in secret_findings)
    assert all(item.severity == "error" for item in secret_findings)


def test_static_checker_resolves_constants_wrappers_templates_and_multilanguage_sources():
    contract = {
        "service": "checkout",
        "spans": [
            {"name": "checkout.request"},
            {"name": "checkout.error"},
            {"name": "checkout.browser_submit"},
            {"name": "checkout.typescript_submit"},
            {"name": "checkout.go_submit"},
            {"name": "checkout.java_submit"},
            {"name": "checkout.csharp_submit"},
            {"name": "checkout.ruby_submit"},
            {"name": "checkout.rust_submit"},
        ],
        "metrics": [
            {"name": "checkout.requests"},
            {"name": "checkout.latency_ms"},
            {"name": "checkout.typescript_requests"},
            {"name": "checkout.go_requests"},
            {"name": "checkout.java_requests"},
            {"name": "checkout.csharp_requests"},
            {"name": "checkout.ruby_requests"},
            {"name": "checkout.rust_requests"},
        ],
        "logs": [
            {"name": "checkout.error"},
            {"name": "checkout.failure"},
            {"name": "checkout.typescript_warning"},
            {"name": "checkout.go_failure"},
            {"name": "checkout.java_failure"},
            {"name": "checkout.csharp_failure"},
            {"name": "checkout.ruby_failure"},
            {"name": "checkout.rust_failure"},
        ],
    }
    findings = check_sources(contract, [ROOT / "tests/fixtures/static_multilang"])
    assert findings == []


def test_static_checker_reports_error_span_api_obligations_with_source_spans():
    contract = {
        "service": "checkout",
        "static_rules": {"require_error_span_observability": True},
        "spans": [
            {
                "name": "checkout.error",
                "fields": {
                    "exception.type": {"type": "string", "required": True},
                    "remediation_hint": {"type": "string", "required": True},
                    "retryable": {"type": "boolean", "required": True},
                },
            }
        ],
    }
    findings = check_sources(contract, [ROOT / "tests/fixtures/static_error_missing.py"])
    codes = {item.code for item in findings}
    assert {
        "static.missing_exception_recording",
        "static.missing_error_status",
        "static.missing_remediation_field",
        "static.inconsistent_retryability",
    } <= codes
    assert all("source_span" in item.details for item in findings if item.code.startswith("static."))


def test_static_checker_accepts_complete_error_span_observability():
    contract = {
        "service": "checkout",
        "static_rules": {
            "require_error_span_observability": True,
            "expected_tracer_names": ["checkout.service"],
            "expected_meter_names": ["checkout.service"],
            "require_metric_metadata": True,
            "require_semconv_attributes": True,
        },
        "spans": [
            {
                "name": "checkout.error",
                "fields": {
                    "exception.type": {"type": "string", "required": True},
                    "remediation_hint": {"type": "string", "required": True},
                    "retryable": {"type": "boolean", "required": True},
                },
            }
        ],
        "metrics": [{"name": "checkout.requests", "unit": "1", "description": "checkout request count"}],
        "logs": [{"name": "checkout.error", "fields": {"trace_id": {"type": "string", "required": True}}}],
    }
    findings = check_sources(contract, [ROOT / "tests/fixtures/static_multilang/python_checkout.py"])
    assert findings == []


def test_static_checker_reports_open_telemetry_api_usage_metadata_gaps():
    contract = {
        "service": "checkout",
        "static_rules": {
            "expected_tracer_names": ["checkout.service"],
            "expected_meter_names": ["checkout.service"],
            "require_metric_metadata": True,
            "require_semconv_attributes": True,
        },
        "spans": [{"name": "checkout.request", "fields": {"http.route": {"type": "string", "required": True}}}],
        "metrics": [{"name": "checkout.requests", "unit": "1", "description": "checkout request count"}],
    }
    findings = check_sources(contract, [ROOT / "tests/fixtures/static_api_gaps.py"])
    codes = {item.code for item in findings}
    assert {
        "static.missing_tracer_name",
        "static.missing_meter_name",
        "static.metric_unit",
        "static.metric_description",
        "static.missing_semconv_attribute",
    } <= codes
