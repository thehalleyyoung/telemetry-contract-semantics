"""Tests for the staged, high-impact improvement pipeline.

Unit tests are fully offline and deterministic (local fixtures only). A
network-gated integration test that clones a real GitHub repository is included
and runs only when ``TELEMETRY_CONTRACTS_NETWORK_TESTS=1`` is set.
"""

from __future__ import annotations

import json
import os
import shutil

import pytest

from telemetry_contracts.cli import main
from telemetry_contracts.pipeline import (
    baseline,
    characterize_repo,
    collect_events,
    diagnose,
    differential,
    instrumentation_plan,
    run_pipeline,
    synthesize_instrumentation,
    telemetry_inventory,
    verify_instrumentation,
)


def _write_repo(tmp_path, *, with_source=True):
    logs = tmp_path / "logs"
    logs.mkdir()
    events = []
    for i in range(12):
        failure = i % 3 == 0
        event = {"kind": "span", "name": "http.request", "service": "api"}
        if failure:
            event["status"] = "error"  # failure, but no correlation / no duration
        else:
            event["trace_id"] = f"t{i}"
            event["duration_ms"] = 5 + i
        events.append(event)
    logs.joinpath("app.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events), encoding="utf-8"
    )
    if with_source:
        src = tmp_path / "src"
        src.mkdir()
        src.joinpath("app.py").write_text(
            "import logging\nfrom opentelemetry import trace\n"
            "from fastapi import FastAPI\napp = FastAPI()\n"
            "@app.route('/x')\ndef x():\n    pass\n",
            encoding="utf-8",
        )
    return tmp_path


def test_telemetry_inventory_counts_kinds_and_correlation():
    events = [
        {"kind": "span", "name": "a", "service": "api", "trace_id": "t1"},
        {"kind": "log", "name": "b", "service": "api"},
    ]
    inv = telemetry_inventory(events)
    assert inv["event_count"] == 2
    assert inv["by_kind"] == {"log": 1, "span": 1}
    assert inv["services"] == ["api"]
    assert inv["correlation_keys"] == ["trace_id"]


def test_characterize_detects_libraries_and_archetype(tmp_path):
    _write_repo(tmp_path)
    report = characterize_repo(str(tmp_path))
    assert report["has_telemetry"] is True
    assert "opentelemetry" in report["instrumentation_libraries"]
    assert "python-logging" in report["instrumentation_libraries"]
    assert report["archetype"] == "http-api"
    assert report["telemetry_inventory"]["services"] == ["api"]
    assert report["manifest"]["commit"] is None  # plain dir, not a git repo


def test_characterize_no_telemetry_gives_next_steps(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    report = characterize_repo(str(tmp_path))
    assert report["has_telemetry"] is False
    assert report["next_steps"]


def test_diagnose_scores_and_lists_unanswered(tmp_path):
    _write_repo(tmp_path)
    events = collect_events(str(tmp_path))["events"]
    report = diagnose(events, service="api")
    assert 0 <= report["diagnosability_score"] <= 100
    assert report["verdict"] == "under-instrumented for incidents"
    gaps = {q["gap"] for q in report["unanswered_questions"]}
    assert "missing-correlation" in gaps
    # leverage is sorted most-blocking first
    affected = [item["events_affected"] for item in report["leverage_ranking"]]
    assert affected == sorted(affected, reverse=True)


def test_diagnose_is_deterministic(tmp_path):
    _write_repo(tmp_path)
    events = collect_events(str(tmp_path))["events"]
    a = json.dumps(diagnose(events, service="api"), sort_keys=True)
    b = json.dumps(diagnose(events, service="api"), sort_keys=True)
    assert a == b


def test_privacy_verdict_dominates():
    events = [
        {"kind": "log", "name": "login", "service": "api", "email": "jane@example.com"},
    ]
    report = diagnose(events)
    assert report["verdict"] == "privacy-risky"


def test_baseline_includes_semantics(tmp_path):
    _write_repo(tmp_path)
    events = collect_events(str(tmp_path))["events"]
    report = baseline(events, service="api")
    assert report["schema"] == "telemetry-contracts/baseline@1"
    assert "model" in report["semantics"]
    assert isinstance(report["order_inferred"], bool)


def test_instrumentation_plan_holds_back_privacy(tmp_path):
    events = [
        {"kind": "log", "name": "login", "service": "api", "email": "jane@example.com"},
        {"kind": "span", "name": "op", "service": "api", "status": "error"},
    ]
    diag = diagnose(events, service="api")
    plan = instrumentation_plan(diag, libraries=["opentelemetry"], max_changes=5)
    # the privacy change must be review-required, not auto-applied
    assert any(c["gap"] == "sensitive-values" for c in plan["review_required_changes"])
    assert all(c["gap"] != "sensitive-values" for c in plan["planned_changes"])
    for change in plan["planned_changes"]:
        assert change["additive_only"] is True
        assert "prompt_pack" in change
        assert change["provenance"]["generator"] == "telemetry-contracts/instrumentation-planner@1"


def test_synthesize_and_verify_closes_gaps(tmp_path):
    _write_repo(tmp_path)
    events = collect_events(str(tmp_path))["events"]
    diag = diagnose(events, service="api")
    plan = instrumentation_plan(diag, max_changes=5)
    applied = synthesize_instrumentation(events, plan)
    assert applied["synthetic"] is True
    assert any(e.get("_synthetic") for e in applied["events"])
    verification = verify_instrumentation(applied["events"], plan)
    assert verification["all_fulfilled"] is True


def test_differential_detects_improvement_and_regression():
    before = {"diagnosability_score": 60, "findings_by_code": {"x": 3},
              "unanswered_questions": [{"id": "which-request"}]}
    after_better = {"diagnosability_score": 90, "findings_by_code": {"x": 1},
                    "unanswered_questions": []}
    diff = differential(before, after_better)
    assert diff["score_delta"] == 30
    assert diff["newly_answerable"] == ["which-request"]
    assert diff["improved"] is True
    assert diff["regressions"] == []

    after_worse = {"diagnosability_score": 50, "findings_by_code": {"x": 3, "y": 2},
                   "unanswered_questions": [{"id": "which-request"}, {"id": "what-error"}]}
    regressed = differential(before, after_worse)
    assert regressed["score_delta"] == -10
    assert regressed["improved"] is False
    assert regressed["regressions"]


def test_run_pipeline_improves_and_keeps_ledger(tmp_path):
    _write_repo(tmp_path)
    report = run_pipeline(str(tmp_path))
    assert report["final"] is not None
    assert report["baseline"]["diagnosability_score"] <= report["final"]["diagnosability_score"]
    assert report["impact_ledger"]
    # every applied round must have non-negative realized delta (no silent regressions)
    for entry in report["impact_ledger"]:
        assert entry["regressions"] == 0


def test_run_pipeline_no_telemetry_is_graceful(tmp_path):
    (tmp_path / "README.md").write_text("nothing here", encoding="utf-8")
    report = run_pipeline(str(tmp_path))
    assert report["final"] is None
    assert report["stopped_reason"] == "no telemetry discovered"


def test_cli_characterize_text(tmp_path, capsys):
    _write_repo(tmp_path)
    assert main(["characterize", "--path", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Archetype: http-api" in out
    assert "opentelemetry" in out


def test_cli_diagnose_fail_under(tmp_path, capsys):
    _write_repo(tmp_path)
    code = main(["diagnose", "--path", str(tmp_path), "--service", "api", "--fail-under", "100"])
    assert code == 1
    out = capsys.readouterr().out
    assert "Diagnosability score:" in out


def test_cli_pipeline_json(tmp_path, capsys):
    _write_repo(tmp_path)
    assert main(["pipeline", "--path", str(tmp_path), "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "telemetry-contracts/pipeline@1"
    assert payload["final"]["diagnosability_score"] >= payload["baseline"]["diagnosability_score"]


@pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)
def test_pipeline_on_real_github_repo(tmp_path):
    from telemetry_contracts.repo_scan import clone_repo

    dest = tmp_path / "repo"
    clone_repo("octocat/Hello-World", dest)
    report = run_pipeline(str(dest))
    assert report["schema"] == "telemetry-contracts/pipeline@1"
    # commit SHA is recoverable from a real clone
    assert report["characterization"]["manifest"]["commit"]
