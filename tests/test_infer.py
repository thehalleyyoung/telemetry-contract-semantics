from telemetry_contracts.infer import infer_contract
from telemetry_contracts.validator import validate_contract_shape


def _events():
    return [
        {"kind": "span", "service": "checkout", "name": "checkout.request", "trace_id": "t1", "attributes": {"tenant_id": "tenant-a", "result": "ok"}},
        {"kind": "span", "service": "checkout", "name": "checkout.request", "trace_id": "t2", "attributes": {"tenant_id": "tenant-b", "result": "error"}},
        {"kind": "metric", "service": "checkout", "name": "checkout.requests", "trace_id": "t1", "value": 1, "tags": {"result": "ok"}},
        {"kind": "log", "service": "checkout", "name": "checkout.error", "request_id": "r1", "severity": "ERROR", "fields": {"error_code": "E1"}},
    ]


def test_inferred_contract_is_lint_clean():
    contract = infer_contract(_events())
    findings = validate_contract_shape(contract)
    assert [f.code for f in findings] == []


def test_inferred_contract_basic_shape():
    contract = infer_contract(_events())
    assert contract["service"] == "checkout"
    span_names = {s["name"] for s in contract["spans"]}
    assert "checkout.request" in span_names
    assert contract["metadata"]["inferred"]["status"].startswith("draft")


def test_ubiquitous_fields_required_others_optional():
    contract = infer_contract(_events())
    request_span = next(s for s in contract["spans"] if s["name"] == "checkout.request")
    # tenant_id present on every span occurrence -> required
    assert request_span["fields"]["tenant_id"]["required"] is True


def test_sensitive_fields_classified_to_avoid_lint_warning():
    contract = infer_contract(_events())
    request_span = next(s for s in contract["spans"] if s["name"] == "checkout.request")
    assert request_span["fields"]["tenant_id"]["sensitivity"] == "sensitive"


def test_ranges_off_by_default_on_by_request():
    events = [
        {"kind": "metric", "service": "a", "name": "m", "value": 5, "tags": {"latency": 100}},
        {"kind": "metric", "service": "a", "name": "m", "value": 9, "tags": {"latency": 200}},
    ]
    default = infer_contract(events)
    metric = next(m for m in default["metrics"] if m["name"] == "m")
    assert "min" not in metric["fields"]["latency"]

    with_ranges = infer_contract(events, infer_ranges=True)
    metric = next(m for m in with_ranges["metrics"] if m["name"] == "m")
    assert metric["fields"]["latency"]["min"] == 100
    assert metric["fields"]["latency"]["max"] == 200


def test_allowed_values_only_for_low_cardinality_non_identifier():
    contract = infer_contract(_events())
    request_span = next(s for s in contract["spans"] if s["name"] == "checkout.request")
    assert request_span["fields"]["result"]["allowed_values"] == ["error", "ok"]


def test_correlation_keys_from_observed_data():
    contract = infer_contract(_events())
    assert "trace_id" in contract["correlation"]["keys"]
    assert "request_id" in contract["correlation"]["keys"]
