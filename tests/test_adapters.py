import json
from pathlib import Path

from telemetry_contracts.adapters import load_events_auto, normalize_event, normalize_events

ROOT = Path(__file__).resolve().parents[1]


def test_normalize_maps_common_aliases():
    event, diagnostics = normalize_event(
        {
            "level": "error",
            "msg": "payment failed",
            "service.name": "checkout",
            "traceId": "abc",
            "dd.span_id": "s1",
            "@timestamp": "2024-05-01T10:00:00.500Z",
            "tenant_id": "tenant-acme",
        },
        line_number=1,
    )
    assert event["kind"] == "log"
    assert event["service"] == "checkout"
    assert event["trace_id"] == "abc"
    assert event["span_id"] == "s1"
    assert event["severity"] == "ERROR"
    assert event["attributes"]["tenant_id"] == "tenant-acme"
    assert isinstance(event["timestamp_ms"], float)
    assert diagnostics == []


def test_kind_inference_confidence_and_fallback():
    span, _ = normalize_event({"name": "op", "duration_ms": 12, "trace_id": "t"})
    assert span["kind"] == "span" and span["_kind_confidence"] == "high"

    metric, _ = normalize_event({"metric_name": "reqs", "value": 5})
    assert metric["kind"] == "metric"

    ambiguous, _ = normalize_event({"foo": "bar"})
    assert ambiguous["kind"] == "event"
    assert ambiguous["_kind_confidence"] == "low"


def test_alias_collision_is_reported_not_silently_dropped():
    _, diagnostics = normalize_event({"trace_id": "a", "traceId": "b", "msg": "x"}, line_number=3)
    assert any(d["code"] == "adapter.alias_collision" and d["canonical"] == "trace_id" for d in diagnostics)


def test_unknown_keys_preserved_as_attributes():
    event, _ = normalize_event({"msg": "hi", "custom_field": 7, "service": "svc"})
    assert event["attributes"]["custom_field"] == 7


def test_load_events_auto_jsonl(tmp_path):
    path = tmp_path / "logs.jsonl"
    path.write_text('{"level":"info","service":"a","msg":"x"}\n{"level":"error","service":"a","msg":"y"}\n', encoding="utf-8")
    loaded = load_events_auto(path)
    assert loaded["format"] == "jsonl"
    assert loaded["summary"]["events"] == 2
    assert loaded["summary"]["services"] == ["a"]


def test_load_events_auto_json_array(tmp_path):
    path = tmp_path / "logs.json"
    path.write_text(json.dumps([{"level": "info", "service": "a", "msg": "x"}]), encoding="utf-8")
    loaded = load_events_auto(path)
    assert loaded["format"] == "json-array"
    assert loaded["summary"]["events"] == 1


def test_load_events_auto_detects_otlp():
    loaded = load_events_auto(ROOT / "examples/otlp/collector_coverage_all_signals.otlp.json")
    assert loaded["format"] == "otlp"
    assert loaded["summary"]["events"] > 0


def test_normalize_events_summary():
    result = normalize_events([{"level": "info", "msg": "a"}, {"value": 1, "metric": "m"}])
    assert result["summary"]["events"] == 2
    assert "log" in result["summary"]["by_kind"]


def test_parse_logfmt_line_basic():
    from telemetry_contracts.adapters import parse_logfmt_line

    parsed = parse_logfmt_line('level=error service=checkout msg="payment failed" trace_id=t1')
    assert parsed["level"] == "error"
    assert parsed["service"] == "checkout"
    assert parsed["msg"] == "payment failed"
    assert parsed["trace_id"] == "t1"


def test_parse_logfmt_line_rejects_prose():
    from telemetry_contracts.adapters import parse_logfmt_line

    assert parse_logfmt_line("this is just a sentence of prose without pairs") is None
    assert parse_logfmt_line("") is None


def test_load_events_auto_logfmt(tmp_path):
    path = tmp_path / "app.logfmt"
    path.write_text(
        'level=info service=a msg="ok" trace_id=t1\n'
        'level=error service=a msg="boom"\n',
        encoding="utf-8",
    )
    loaded = load_events_auto(path)
    assert loaded["format"] == "logfmt"
    assert loaded["summary"]["events"] == 2


def test_load_events_auto_tolerant_skips_bad_lines(tmp_path):
    path = tmp_path / "mixed.log"
    path.write_text(
        '{"kind":"log","name":"a","service":"s"}\n'
        'a line of unparseable prose with no structure at all\n'
        'level=warn service=s msg="slow"\n',
        encoding="utf-8",
    )
    loaded = load_events_auto(path, tolerant=True)
    assert loaded["summary"]["events"] == 2
    assert any(d.get("code") == "adapter.unparsed_line" for d in loaded["diagnostics"])
