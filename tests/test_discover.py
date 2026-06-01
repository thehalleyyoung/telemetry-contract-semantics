from telemetry_contracts.discover import analyze_events
from telemetry_contracts.findings import TAXONOMY


def test_detects_raw_secret_in_arbitrary_log():
    report = analyze_events([{"kind": "log", "name": "x", "severity": "INFO", "attributes": {"authorization": "Bearer abcdef1234567890"}}])
    codes = {f["code"] for f in report["findings"]}
    assert "telemetry.sensitive_value" in codes
    assert report["summary"]["by_severity"]["error"] >= 1


def test_detects_email_value():
    report = analyze_events([{"kind": "log", "name": "x", "attributes": {"contact": "jane.doe@example.com"}}])
    assert any(f["code"] == "telemetry.sensitive_value" for f in report["findings"])


def test_structural_ids_are_not_false_positives():
    report = analyze_events([{"kind": "span", "name": "x", "attributes": {"parent_span_id": "1111222233334444"}}])
    assert all(f["code"] != "telemetry.sensitive_value" for f in report["findings"])


def test_secret_in_non_correlation_id_field_is_not_masked():
    jwt = "eyJabcdefgh.eyJ1234567890.signature123456"
    for field in ("session_id", "trace_id"):
        clean = analyze_events([{"kind": "log", "name": "x", "attributes": {field: jwt}}])
        assert all(f["code"] != "telemetry.sensitive_value" for f in clean["findings"]), field
    for field in ("auth_id", "token_id", "user_id"):
        flagged = analyze_events([{"kind": "log", "name": "x", "attributes": {field: jwt}}])
        assert any(f["code"] == "telemetry.sensitive_value" for f in flagged["findings"]), field


def test_flags_unclassified_tenant_identifier():
    report = analyze_events([{"kind": "log", "name": "x", "attributes": {"tenant_id": "tenant-acme"}}])
    assert any(f["code"] == "telemetry.sensitive_unclassified" for f in report["findings"])


def test_failure_without_correlation_or_error_evidence():
    report = analyze_events([{"kind": "log", "name": "boom", "severity": "ERROR", "attributes": {}}])
    codes = {f["code"] for f in report["findings"]}
    assert "telemetry.correlation_missing" in codes
    assert "discovery.missing_error_evidence" in codes


def test_failure_with_error_evidence_and_correlation_is_clean():
    report = analyze_events([{"kind": "log", "name": "boom", "severity": "ERROR", "trace_id": "t1", "attributes": {"error_code": "E1"}}])
    codes = {f["code"] for f in report["findings"]}
    assert "telemetry.correlation_missing" not in codes
    assert "discovery.missing_error_evidence" not in codes


def test_low_confidence_kind_skips_failure_checks():
    report = analyze_events([{"kind": "event", "_kind_confidence": "low", "name": "x", "attributes": {"result": "error"}}])
    assert all(f["code"] not in {"telemetry.correlation_missing", "discovery.missing_error_evidence"} for f in report["findings"])


def test_high_cardinality_metric_label():
    events = [
        {"kind": "metric", "name": "reqs", "service": "a", "value": 1, "tags": {"user": f"u{i}"}}
        for i in range(60)
    ]
    report = analyze_events(events)
    assert any(f["code"] == "telemetry.cardinality" for f in report["findings"])


def test_small_sample_does_not_trigger_cardinality():
    events = [{"kind": "metric", "name": "reqs", "service": "a", "value": 1, "tags": {"user": f"u{i}"}} for i in range(5)]
    report = analyze_events(events)
    assert all(f["code"] != "telemetry.cardinality" for f in report["findings"])


def test_all_emitted_codes_are_in_taxonomy():
    events = [
        {"kind": "log", "name": "boom", "severity": "ERROR", "attributes": {"authorization": "Bearer abcdef1234567890", "tenant_id": "tenant-x"}},
    ]
    report = analyze_events(events)
    for finding in report["findings"]:
        assert finding["code"] in TAXONOMY


def test_examples_are_capped_per_code():
    events = [{"kind": "log", "name": "x", "severity": "ERROR", "attributes": {"email": "a@b.com"}} for _ in range(100)]
    report = analyze_events(events)
    shown = sum(1 for f in report["findings"] if f["code"] == "telemetry.sensitive_value")
    assert shown <= 25
    assert report["summary"]["by_code"]["telemetry.sensitive_value"] == 100
