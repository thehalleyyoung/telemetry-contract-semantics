import time
import tracemalloc

from telemetry_contracts.otlp import convert_otlp_payload_with_diagnostics
from telemetry_contracts.validator import validate_events


def test_event_index_validates_100k_jsonl_events_within_documented_budget():
    contract = {
        "version": "1.0",
        "service": "checkout",
        "metrics": [{"name": "checkout.requests", "value": {"type": "number", "min": 0}}],
        "logs": [{"name": "checkout.done", "fields": {"trace_id": {"type": "string", "required": True}}}],
    }
    events = [
        {
            "kind": "metric",
            "service": "checkout",
            "name": "checkout.requests",
            "value": 1,
            "timestamp_ms": i,
            "tags": {"trace_id": f"trace-{i % 1000}", "tenant_id": f"tenant-{i % 25}"},
        }
        for i in range(99_999)
    ]
    events.append({"kind": "log", "service": "checkout", "name": "checkout.done", "timestamp_ms": 100_000, "fields": {"trace_id": "trace-final"}})

    tracemalloc.start()
    started = time.perf_counter()
    findings = validate_events(contract, events)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert findings == []
    assert elapsed < 30.0
    assert peak < 220 * 1024 * 1024


def test_large_otlp_export_conversion_within_documented_budget():
    spans = [
        {
            "traceId": f"{i:032x}",
            "spanId": f"{i % (16**16):016x}",
            "name": "checkout.request",
            "startTimeUnixNano": str(1_700_000_000_000_000_000 + i),
            "endTimeUnixNano": str(1_700_000_000_000_001_000 + i),
            "attributes": [{"key": "tenant_id", "value": {"stringValue": f"tenant-{i % 50}"}}],
        }
        for i in range(8_000)
    ]
    payload = {
        "resourceSpans": [
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "checkout"}}]},
                "scopeSpans": [{"scope": {"name": "checkout.service"}, "spans": spans}],
            }
        ]
    }

    tracemalloc.start()
    started = time.perf_counter()
    report = convert_otlp_payload_with_diagnostics(payload)
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert report["summary"]["events"] == 8_000
    assert report["diagnostics"] == []
    assert elapsed < 20.0
    assert peak < 160 * 1024 * 1024
