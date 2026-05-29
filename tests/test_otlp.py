from pathlib import Path

from telemetry_contracts.otlp import convert_otlp_payload, load_otlp_json
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
