"""Tests for inferring execution semantics on arbitrary existing projects."""

from __future__ import annotations

import json

from telemetry_contracts.cli import main
from telemetry_contracts.infer import infer_contract, infer_temporal_order
from telemetry_contracts.project_semantics import (
    align_runtime_with_source,
    find_source_files,
    group_events_by_service,
    infer_execution_semantics,
)
from telemetry_contracts.repo_scan import scan_directory
from telemetry_contracts.validator import validate_contract_shape


def _ordered_events(groups: int = 4) -> list[dict]:
    events: list[dict] = []
    for i in range(groups):
        base = i * 1000
        events += [
            {"kind": "span", "name": "http.request", "service": "api", "trace_id": f"t{i}", "timestamp_ms": base},
            {"kind": "span", "name": "db.query", "service": "api", "trace_id": f"t{i}", "timestamp_ms": base + 10},
            {"kind": "log", "name": "completed", "service": "api", "trace_id": f"t{i}", "timestamp_ms": base + 20},
        ]
    return events


def test_infer_temporal_order_linear_chain():
    order = infer_temporal_order(_ordered_events())
    assert order is not None
    assert order["correlation_key"] == "trace_id"
    assert [step["name"] for step in order["steps"]] == ["http.request", "db.query", "completed"]
    assert order["enforceable"] is True
    assert order["partial_groups"] == 0
    assert order["window_ms"] == 20


def test_infer_temporal_order_requires_two_groups():
    events = [
        {"kind": "span", "name": "a", "trace_id": "only", "timestamp_ms": 0},
        {"kind": "span", "name": "b", "trace_id": "only", "timestamp_ms": 1},
    ]
    assert infer_temporal_order(events) is None


def test_infer_temporal_order_ambiguous_returns_none():
    # Two groups disagree on the order of a and b -> no confident edge.
    events = [
        {"kind": "span", "name": "a", "trace_id": "g1", "timestamp_ms": 0},
        {"kind": "span", "name": "b", "trace_id": "g1", "timestamp_ms": 5},
        {"kind": "span", "name": "a", "trace_id": "g2", "timestamp_ms": 5},
        {"kind": "span", "name": "b", "trace_id": "g2", "timestamp_ms": 0},
    ]
    assert infer_temporal_order(events) is None


def test_infer_contract_with_sequences_is_lint_clean():
    contract = infer_contract(_ordered_events(), infer_sequences=True)
    sequences = contract.get("temporal_sequences")
    assert sequences and sequences[0]["required"] is False
    assert sequences[0]["group_by"] == ["trace_id"]
    assert [step["name"] for step in sequences[0]["steps"]] == [
        "http.request",
        "db.query",
        "completed",
    ]
    # Inferred sequence must not introduce schema/shape errors.
    errors = [f for f in validate_contract_shape(contract) if f.severity == "error"]
    assert errors == []


def test_infer_contract_default_has_no_sequences():
    contract = infer_contract(_ordered_events())
    assert "temporal_sequences" not in contract


def test_inferred_sequence_ignores_non_signal_kinds():
    # Workflow records normalized to kind="event" must never become sequence
    # steps (the schema enum only allows span/log/metric).
    events: list[dict] = []
    for i in range(4):
        base = i * 1000
        events += [
            {"kind": "event", "name": "start", "request_id": f"r{i}", "timestamp_ms": base},
            {"kind": "event", "name": "finish", "request_id": f"r{i}", "timestamp_ms": base + 5},
        ]
    assert infer_temporal_order(events) is None
    contract = infer_contract(events, infer_sequences=True)
    assert "temporal_sequences" not in contract
    errors = [f for f in validate_contract_shape(contract) if f.severity == "error"]
    assert all("temporal" not in f.contract_path for f in errors if f.contract_path)


def test_infer_execution_semantics_aligns_with_checker():
    report = infer_execution_semantics(_ordered_events(), service="api")
    assert report["schema"] == "telemetry-contracts/execution-semantics@1"
    assert report["semantics"]["aligned_with_checker"] is True
    assert report["semantics"]["pass"] is True
    assert report["inferred_ordering"]["enforceable"] is True
    assert report["event_structure"]["node_count"] == 12


def test_group_events_by_service_buckets_unspecified():
    events = [
        {"kind": "span", "name": "a", "service": "api"},
        {"kind": "span", "name": "b"},
    ]
    grouped = group_events_by_service(events)
    assert set(grouped) == {"api", "(unspecified)"}


def test_find_source_files_and_alignment(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text('tracer.start_span("http.request")\n', encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.py").write_text("noise", encoding="utf-8")

    sources = find_source_files(str(tmp_path))
    assert any(path.endswith("app.py") for path in sources)
    assert all("node_modules" not in path for path in sources)

    contract = infer_contract(_ordered_events())
    alignment = align_runtime_with_source(contract, sources)
    assert "http.request" in alignment["located_in_source"]
    assert alignment["expected_signals"] >= 1


def test_cli_infer_semantics_text(tmp_path, capsys):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        "\n".join(json.dumps(event) for event in _ordered_events()), encoding="utf-8"
    )
    exit_code = main(["infer-semantics", "--events", str(events_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Execution semantics for service: api" in out
    assert "inferred order (trace_id): span:http.request -> span:db.query -> log:completed" in out


def test_cli_infer_semantics_json(tmp_path, capsys):
    events_path = tmp_path / "events.jsonl"
    events_path.write_text(
        "\n".join(json.dumps(event) for event in _ordered_events()), encoding="utf-8"
    )
    exit_code = main(["infer-semantics", "--events", str(events_path), "--format", "json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["semantics"]["aligned_with_checker"] is True
    assert payload["inferred_ordering"]["steps"][0]["name"] == "http.request"


def test_scan_deep_includes_semantics(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    logs.joinpath("events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in _ordered_events()), encoding="utf-8"
    )
    src = tmp_path / "src"
    src.mkdir()
    src.joinpath("app.py").write_text('tracer.start_span("http.request")\n', encoding="utf-8")

    report = scan_directory(str(tmp_path), deep=True)
    assert "semantics" in report
    services = {entry["service"] for entry in report["semantics"]["services"]}
    assert "api" in services
    api = next(entry for entry in report["semantics"]["services"] if entry["service"] == "api")
    assert api["inferred_ordering"]["steps"] == [
        "span:http.request",
        "span:db.query",
        "log:completed",
    ]
    alignment = next(
        entry for entry in report["semantics"]["source_alignment"] if entry["service"] == "api"
    )
    assert "http.request" in alignment["located_in_source"]


def test_scan_without_deep_has_no_semantics(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    logs.joinpath("events.jsonl").write_text(
        "\n".join(json.dumps(event) for event in _ordered_events()), encoding="utf-8"
    )
    report = scan_directory(str(tmp_path))
    assert "semantics" not in report
