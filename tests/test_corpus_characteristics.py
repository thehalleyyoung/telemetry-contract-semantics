"""Offline tests for repo-characteristic detection, correlation, and SVG plots."""

from __future__ import annotations

from pathlib import Path
from xml.dom import minidom

from telemetry_contracts.mining.characteristics import (
    detect_characteristics,
    detect_instrumentation,
    detect_language,
)
from telemetry_contracts.mining.correlate import correlate, render_correlation_markdown
from telemetry_contracts.mining.plots import render_plots


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_detect_language_picks_majority(tmp_path):
    _write(tmp_path, "a.py", "x=1\n")
    _write(tmp_path, "b.py", "y=2\n")
    _write(tmp_path, "c.js", "var z=3\n")
    result = detect_language(tmp_path)
    assert result["language"] == "Python"
    assert result["counts"] == {"JavaScript": 1, "Python": 2}


def test_detect_language_ignores_vendor_dirs(tmp_path):
    _write(tmp_path, "node_modules/dep/index.js", "x\n")
    _write(tmp_path, "app.py", "x=1\n")
    assert detect_language(tmp_path)["language"] == "Python"


def test_detect_instrumentation_from_manifest(tmp_path):
    _write(tmp_path, "requirements.txt", "flask==2.0\nopentelemetry-sdk==1.0\n")
    result = detect_instrumentation(tmp_path)
    assert result["instrumentation_present"] is True
    assert "opentelemetry" in result["instrumentation_libraries"]


def test_detect_instrumentation_absent(tmp_path):
    _write(tmp_path, "requirements.txt", "flask==2.0\n")
    assert detect_instrumentation(tmp_path)["instrumentation_present"] is False


def test_detect_characteristics_is_deterministic(tmp_path):
    _write(tmp_path, "app.py", "x=1\n")
    _write(tmp_path, "package.json", '{"dependencies":{"winston":"3.0"}}')
    first = detect_characteristics(tmp_path)
    second = detect_characteristics(tmp_path)
    assert first == second
    assert first["language"] == "Python"
    assert first["instrumentation_present"] is True
    assert "winston" in first["instrumentation_libraries"]


_ROWS = [
    {"language": "Python", "has_telemetry": True, "failure_events": 2,
     "headline_blocked": True, "diagnosability_score": 40, "event_count": 500,
     "instrumentation_present": False},
    {"language": "Python", "has_telemetry": True, "failure_events": 0,
     "headline_blocked": False, "diagnosability_score": 95, "event_count": 12000,
     "instrumentation_present": True},
    {"language": "Go", "has_telemetry": False, "failure_events": 0,
     "headline_blocked": False, "diagnosability_score": None, "event_count": 0,
     "instrumentation_present": True},
]


def test_correlate_breakdowns_and_determinism():
    first = correlate(_ROWS)
    assert first == correlate(list(_ROWS))
    assert set(first["by_language"]) == {"Go", "Python"}
    assert set(first["by_instrumentation"]) == {"absent", "present"}
    py = first["by_language"]["Python"]
    assert py["subjects"] == 2
    assert py["with_failures"] == 1
    assert py["cannot_answer"] == 1
    assert py["cannot_answer_permille"] == 1000  # 1 of 1 failure-bearing
    # Volume buckets are the fixed boundaries.
    assert set(first["by_event_volume"]).issubset({"0", "1-99", "100-999", "1k-9999", "10k+"})


def test_correlate_accepts_full_dataset():
    dataset = {"subjects": _ROWS}
    assert correlate(dataset)["subjects_total"] == 3


def test_render_correlation_markdown_is_stable():
    md = render_correlation_markdown(correlate(_ROWS))
    assert "# Gap prevalence by repository characteristic" in md
    assert md == render_correlation_markdown(correlate(_ROWS))
    assert md.endswith("\n")


def test_plots_are_wellformed_and_deterministic():
    dataset = {
        "bug_class_prevalence": {},
        "subjects": [
            {"diagnosability_score": 30, "has_telemetry": True},
            {"diagnosability_score": 85, "has_telemetry": True},
            {"diagnosability_score": None, "has_telemetry": False},
        ],
    }
    plots = render_plots(dataset)
    assert set(plots) == {"score_distribution.svg", "bug_class_prevalence.svg"}
    for svg in plots.values():
        minidom.parseString(svg)  # raises if malformed
        assert "<svg" in svg
    assert plots == render_plots(dataset)


def test_plots_handle_empty_dataset():
    plots = render_plots({"bug_class_prevalence": {}, "subjects": []})
    for svg in plots.values():
        minidom.parseString(svg)
