from pathlib import Path

from telemetry_contracts.otlp import (
    analyze_otlp_report,
    convert_events_to_otlp_payload,
    convert_otlp_payload,
    convert_otlp_payload_with_diagnostics,
    load_otlp_json,
    load_otlp_json_detailed,
    load_otlp_jsonl_detailed,
    load_otlp_jsonl_stream,
)
from telemetry_contracts.validator import validate_events
from telemetry_contracts.loader import load_contract


ROOT = Path(__file__).resolve().parents[1]


def test_otlp_case_study_confirms_missing_tenant_bug():
    contract = load_contract(ROOT / "examples/real_world/otel_checkout_missing_tenant.contract.json")
    events = load_otlp_json(ROOT / "examples/real_world/otel_checkout_missing_tenant.otlp.json")

    findings = validate_events(contract, events)

    assert any(f.code == "telemetry.missing_field" and "tenant_id" in f.message for f in findings)


def test_otlp_histogram_and_summary_points_preserve_aggregation_metadata():
    events = convert_otlp_payload(
        {
            "resourceMetrics": [
                {
                    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "checkout"}}]},
                    "scopeMetrics": [
                        {
                            "metrics": [
                                {
                                    "name": "checkout.duration",
                                    "histogram": {
                                        "aggregationTemporality": "AGGREGATION_TEMPORALITY_DELTA",
                                        "dataPoints": [
                                            {
                                                "count": "3",
                                                "sum": 42.5,
                                                "min": 2,
                                                "max": 30,
                                                "bucketCounts": ["1", "2"],
                                                "explicitBounds": [10],
                                                "attributes": [{"key": "route", "value": {"stringValue": "/checkout"}}],
                                            }
                                        ],
                                    },
                                },
                                {
                                    "name": "checkout.payload",
                                    "summary": {
                                        "dataPoints": [
                                            {
                                                "count": 2,
                                                "sum": "7.5",
                                                "quantileValues": [
                                                    {"quantile": 0.5, "value": 3.0},
                                                    {"quantile": 0.99, "value": "4.5"},
                                                ],
                                            }
                                        ]
                                    },
                                },
                            ]
                        }
                    ],
                }
            ]
        }
    )

    histogram = events[0]
    assert histogram["service"] == "checkout"
    assert histogram["metric_type"] == "histogram"
    assert histogram["value"] == 42.5
    assert histogram["count"] == 3
    assert histogram["bucket_counts"] == [1, 2]
    assert histogram["explicit_bounds"] == [10]
    assert histogram["tags"]["route"] == "/checkout"
    summary = events[1]
    assert summary["metric_type"] == "summary"
    assert summary["value"] == 7.5
    assert summary["quantiles"][-1] == {"quantile": 0.99, "value": 4.5}


def test_otlp_collector_fixture_preserves_span_log_metric_correlation():
    report = load_otlp_json_detailed(ROOT / "examples/otlp/collector_mixed_signals.otlp.json")
    contract = load_contract(ROOT / "examples/otlp/collector_mixed_signals.contract.json")

    assert report["summary"]["events_by_kind"] == {"log": 1, "metric": 1, "span": 1}
    assert report["summary"]["invalidating_diagnostics"] == 0
    assert not validate_events(contract, report["events"])

    span = next(event for event in report["events"] if event["kind"] == "span")
    assert span["parent_span_id"] == "aaaaaaaaaaaaaaaa"
    assert span["events"][0]["name"] == "payment.authorize.start"
    assert span["links"][0]["trace_id"] == "99999999999999999999999999999999"
    assert span["status"]["code"] == "STATUS_CODE_OK"
    assert span["scope"]["name"] == "checkout.instrumentation"
    assert span["source_json_path"].endswith(".spans[0]")

    metric = next(event for event in report["events"] if event["kind"] == "metric")
    assert metric["trace_id"] == span["trace_id"]
    assert metric["span_id"] == span["span_id"]
    assert metric["exemplars"][0]["filtered_attributes"] == {"sampling": "head"}
    assert metric["timestamp_ms"] == 1700000000123

    log = next(event for event in report["events"] if event["kind"] == "log")
    assert log["observed_time_unix_nano"] == 1700000000130000000
    assert log["severity_number"] == 17
    assert log["body"] == {"message": "payment authorized after retry", "retry": True}
    assert log["message"] == "payment authorized after retry"
    assert log["fields"]["retry"] is True


def test_otlp_jsonl_streaming_and_alias_diagnostics_are_equivalent():
    path = ROOT / "examples/otlp/collector_stream_aliases.otlp.jsonl"

    detailed = load_otlp_jsonl_detailed(path)
    streamed = list(load_otlp_jsonl_stream(path))

    assert streamed == detailed["events"]
    assert detailed["summary"]["streaming"] is True
    assert detailed["summary"]["events_by_kind"] == {"log": 1, "span": 1}
    assert detailed["summary"]["diagnostics_by_code"]["otlp.normalized_alias"] >= 8
    assert detailed["summary"]["invalidating_diagnostics"] == 0
    assert detailed["events"][0]["trace_id"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert detailed["events"][1]["message"] == "stream import reached checkout"


def test_otlp_diagnostics_mark_dropped_or_skipped_evidence_as_invalidating():
    report = convert_otlp_payload_with_diagnostics(
        {
            "resourceSpans": [
                {
                    "resource": {"attributes": [{"value": {"stringValue": "missing-key"}}]},
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "name": "checkout.pay",
                                    "traceId": "trace",
                                    "spanId": "span",
                                    "droppedAttributesCount": "2",
                                    "attributes": [{"key": "tenant_id", "value": {"stringValue": "tenant-public"}}],
                                },
                                "not-an-object",
                            ]
                        }
                    ],
                }
            ],
            "unknownTopLevel": True,
        }
    )

    assert len(report["events"]) == 1
    assert report["summary"]["invalidating_diagnostics"] == 3
    assert report["summary"]["diagnostics_by_code"]["otlp.dropped_evidence"] == 1
    assert report["summary"]["diagnostics_by_code"]["otlp.skipped_record"] == 2
    assert report["summary"]["diagnostics_by_code"]["otlp.unsupported_top_level"] == 1


def test_collector_coverage_fixture_exercises_otlp_signals_and_analysis():
    report = load_otlp_json_detailed(ROOT / "examples/otlp/collector_coverage_all_signals.otlp.json")
    analysis = analyze_otlp_report(report)

    metric_types = {event["metric_type"] for event in report["events"] if event["kind"] == "metric"}
    assert {"sum", "gauge", "histogram", "exponentialHistogram", "summary"} <= metric_types
    assert report["summary"]["events_by_kind"] == {"log": 1, "metric": 5, "span": 1}
    assert report["summary"]["diagnostics_by_code"]["otlp.dropped_evidence"] == 2
    assert report["summary"]["diagnostics_by_code"]["otlp.unsupported_metric"] == 1
    assert analysis["summary"]["cardinality_risks"] >= 4
    assert analysis["summary"]["pii_secret_risks"] == 1
    assert analysis["summary"]["unknown_schemas"] == 1
    assert analysis["temporality"]["counts"]["AGGREGATION_TEMPORALITY_DELTA"] == 2


def test_otlp_jsonl_malformed_records_are_diagnostic_fixtures():
    report = load_otlp_jsonl_detailed(ROOT / "examples/otlp/collector_malformed_records.otlp.jsonl")

    assert report["summary"]["events"] == 0
    assert report["summary"]["invalidating_diagnostics"] == 3
    assert report["summary"]["diagnostics_by_code"]["otlp.malformed_record"] == 2
    assert report["summary"]["diagnostics_by_code"]["otlp.skipped_record"] == 1


def test_contract_jsonl_round_trip_converter_preserves_importer_semantics():
    original = load_otlp_json(ROOT / "examples/otlp/collector_mixed_signals.otlp.json")
    payload = convert_events_to_otlp_payload(original)
    round_tripped = convert_otlp_payload(payload)

    assert [event["kind"] for event in round_tripped] == [event["kind"] for event in original]
    assert {event["name"] for event in round_tripped} == {event["name"] for event in original}
    assert {event.get("trace_id") for event in round_tripped} == {event.get("trace_id") for event in original}
    assert any(event.get("exemplars") for event in round_tripped if event["kind"] == "metric")
