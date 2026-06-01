"""Offline tests for the browser-playground engine entrypoint and bundle build.

``analyze_text`` is the single function the zero-install Pyodide playground calls
client-side. It must auto-detect the visitor's telemetry format, return the score
and gaps, and be byte-deterministic (so URL-shareable playground results are
reproducible). The bundle build must be byte-deterministic too, so the committed
zip can be diffed in CI.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from telemetry_contracts.playground import analyze_text

_ROOT = Path(__file__).resolve().parents[1]


def _jsonl(events: list[dict]) -> str:
    return "\n".join(json.dumps(e) for e in events)


def test_detects_jsonl_and_scores_failure_without_correlation():
    text = _jsonl(
        [
            {"kind": "span", "name": "checkout", "service": "s", "status": "error", "fields": {"tenant_id": "a"}},
            {"kind": "log", "name": "checkout.error", "service": "s", "severity": "ERROR", "fields": {"tenant_id": "a"}},
        ]
    )
    report = analyze_text(text)
    assert report["schema"] == "telemetry-contracts/playground@1"
    assert report["format"] == "jsonl"
    assert report["event_count"] == 2
    assert report["has_telemetry"] is True
    assert 0 <= report["diagnosability_score"] <= 100
    codes = {g["code"] for g in report["top_gaps"]}
    assert "telemetry.correlation_missing" in codes


def test_top_gaps_sorted_by_count_then_code():
    text = _jsonl([{"kind": "log", "name": "e", "service": "s", "severity": "ERROR", "fields": {"email": f"u{i}@x.com"}} for i in range(3)])
    report = analyze_text(text)
    counts = [g["count"] for g in report["top_gaps"]]
    assert counts == sorted(counts, reverse=True)
    # tie-break by code
    same_count = [g for g in report["top_gaps"] if g["count"] == (counts[0] if counts else 0)]
    assert [g["code"] for g in same_count] == sorted(g["code"] for g in same_count)


def test_parses_logfmt():
    report = analyze_text("level=error msg=boom service=s\nlevel=info msg=ok service=s", source_name="x.logfmt")
    assert report["format"] == "logfmt"
    assert report["event_count"] == 2


def test_parses_json_array():
    text = json.dumps([{"kind": "log", "name": "a", "service": "s", "severity": "INFO"}])
    report = analyze_text(text, source_name="x.json")
    assert report["event_count"] == 1


def test_empty_input_is_safe():
    report = analyze_text("")
    assert report["has_telemetry"] is False
    assert report["event_count"] == 0


def test_tolerant_of_garbage_lines():
    text = "not json at all\n{\"kind\":\"log\",\"name\":\"a\",\"service\":\"s\",\"severity\":\"ERROR\"}"
    report = analyze_text(text)
    # The valid line is still analyzed; the garbage line is recorded, not fatal.
    assert report["event_count"] >= 1


def test_byte_deterministic():
    text = _jsonl([{"kind": "span", "name": "x", "service": "s", "status": "error"} for _ in range(5)])
    a = json.dumps(analyze_text(text), sort_keys=True)
    b = json.dumps(analyze_text(text), sort_keys=True)
    assert a == b


def test_service_filter():
    text = _jsonl(
        [
            {"kind": "log", "name": "a", "service": "x", "severity": "ERROR"},
            {"kind": "log", "name": "b", "service": "y", "severity": "ERROR"},
        ]
    )
    full = analyze_text(text)
    only_x = analyze_text(text, service="x")
    assert only_x["service"] == "x"
    assert only_x["event_count"] <= full["event_count"]


def _load_build_module():
    spec = importlib.util.spec_from_file_location("playground_build", _ROOT / "playground" / "build.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["playground_build"] = module
    spec.loader.exec_module(module)
    return module


def test_bundle_build_is_byte_deterministic(tmp_path, monkeypatch):
    build = _load_build_module()
    bundle = Path(build._ASSETS) / "telemetry_contracts.zip"
    build.build_bundle()
    first = bundle.read_bytes()
    build.build_bundle()
    second = bundle.read_bytes()
    assert first == second
    # The bundle must contain the playground entrypoint the browser imports.
    import zipfile

    with zipfile.ZipFile(bundle) as zf:
        names = set(zf.namelist())
    assert "telemetry_contracts/playground.py" in names
    assert "telemetry_contracts/__init__.py" in names


def test_examples_index_is_valid_and_files_exist():
    build = _load_build_module()
    build.build_bundle()
    assets = Path(build._ASSETS)
    index = json.loads((assets / "examples.json").read_text())
    assert len(index) >= 4
    for entry in index:
        assert {"id", "title", "description", "file"} <= set(entry)
        assert (assets / entry["file"]).exists()
