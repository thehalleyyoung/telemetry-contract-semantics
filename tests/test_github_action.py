"""Offline tests for the GitHub Action / CI surface.

Covers the deterministic CI report, the configurable score-floor + severity gate,
the base-branch score diff, the PR comment rendering, and an end-to-end test of
the Action's underlying command path (ci-report JSON + markdown and scan -> SARIF)
asserting the payloads are well-formed and byte-deterministic. No network.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from telemetry_contracts.github_action import (
    analyze_for_ci,
    build_pr_comment,
    compare_ci_reports,
    evaluate_ci_gate_for_report,
)


def _write_repo(root: Path) -> None:
    logs = root / "logs"
    logs.mkdir(parents=True)
    events = []
    for i in range(12):
        e = {"kind": "span", "name": "http.request", "service": "svc"}
        if i % 3 == 0:
            e["status"] = "error"
        else:
            e["trace_id"] = f"t{i}"
            e["duration_ms"] = 10 + i
        events.append(e)
    (logs / "app.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    (root / "app.py").write_text("import logging\nlogger = logging.getLogger(__name__)\n", encoding="utf-8")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _write_repo(tmp_path)
    return tmp_path


def test_analyze_for_ci_is_deterministic(repo: Path):
    a = analyze_for_ci(repo)
    b = analyze_for_ci(repo)
    assert a == b
    assert a["schema"] == "telemetry-contracts/ci-report@1"
    assert isinstance(a["diagnosability_score"], int)
    assert a["findings_total"] >= 1
    assert a["has_telemetry"] is True


def test_top_gaps_sorted_by_count_then_code(repo: Path):
    report = analyze_for_ci(repo)
    counts = [g["count"] for g in report["top_gaps"]]
    assert counts == sorted(counts, reverse=True)
    for gap in report["top_gaps"]:
        assert set(gap.keys()) == {"code", "count", "severity"}


def test_gate_score_floor(repo: Path):
    report = analyze_for_ci(repo)
    score = report["diagnosability_score"]
    assert evaluate_ci_gate_for_report(report, min_score=score)["pass"] is True
    failing = evaluate_ci_gate_for_report(report, min_score=score + 1)
    assert failing["pass"] is False
    assert any("below the floor" in r for r in failing["reasons"])


def test_gate_severity_threshold(repo: Path):
    report = analyze_for_ci(repo)
    # The fixture yields warning-severity findings; fail-on=warning should fail,
    # fail-on=error and fail-on=never should pass.
    assert evaluate_ci_gate_for_report(report, fail_on="warning")["pass"] is False
    assert evaluate_ci_gate_for_report(report, fail_on="error")["pass"] is True
    assert evaluate_ci_gate_for_report(report, fail_on="never")["pass"] is True


def test_compare_reports_score_delta_and_gap_sets(repo: Path):
    head = analyze_for_ci(repo)
    base = dict(head)
    base["diagnosability_score"] = head["diagnosability_score"] - 15
    base["top_gaps"] = []
    cmp = compare_ci_reports(head, base)
    assert cmp["score_delta"] == 15
    assert cmp["new_gap_codes"] == sorted(g["code"] for g in head["top_gaps"])
    assert cmp["resolved_gap_codes"] == []


def test_pr_comment_is_well_formed_and_deterministic(repo: Path):
    report = analyze_for_ci(repo)
    base = dict(report)
    base["diagnosability_score"] = report["diagnosability_score"] - 10
    c1 = build_pr_comment(report, base)
    c2 = build_pr_comment(report, base)
    assert c1 == c2
    assert c1.startswith("## 🔭 Observability report")
    assert "Diagnosability score:" in c1
    assert "vs base" in c1
    assert "correctness property" in c1


def test_no_telemetry_report(tmp_path: Path):
    (tmp_path / "README.md").write_text("# empty\n", encoding="utf-8")
    report = analyze_for_ci(tmp_path)
    assert report["has_telemetry"] is False
    assert report["diagnosability_score"] is None
    comment = build_pr_comment(report)
    assert "No telemetry was discovered" in comment
    # An empty repo trivially passes the severity gate.
    assert evaluate_ci_gate_for_report(report, fail_on="error")["pass"] is True


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "telemetry_contracts.cli", *args],
        capture_output=True,
        text=True,
    )


def test_end_to_end_action_command_path(repo: Path, tmp_path: Path):
    """Exercise the exact command path the composite Action runs."""

    report_json = tmp_path / "report.json"
    comment_md = tmp_path / "comment.md"
    findings_json = tmp_path / "findings.json"
    sarif_out = tmp_path / "results.sarif"

    # 1. ci-report JSON with a gate (fail-on never -> exit 0).
    rc = _run_cli(
        "ci-report", "--path", str(repo), "--fail-on", "never",
        "--format", "json", "--output", str(report_json),
    )
    assert rc.returncode == 0, rc.stderr
    report = json.loads(report_json.read_text())
    assert report["gate"]["pass"] is True
    assert "diagnosability_score" in report

    # 2. ci-report markdown PR comment.
    rc = _run_cli(
        "ci-report", "--path", str(repo), "--fail-on", "never",
        "--format", "markdown", "--output", str(comment_md),
    )
    assert rc.returncode == 0, rc.stderr
    comment = comment_md.read_text()
    assert comment.startswith("## 🔭 Observability report")

    # 3. scan -> SARIF, asserting a well-formed SARIF 2.1.0 document.
    rc = _run_cli(
        "scan", "--path", str(repo), "--format", "json",
        "--output", str(findings_json), "--fail-on", "never",
    )
    assert rc.returncode == 0, rc.stderr
    rc = _run_cli("sarif", "--findings", str(findings_json), "--output", str(sarif_out))
    assert rc.returncode == 0, rc.stderr
    sarif = json.loads(sarif_out.read_text())
    assert sarif["version"] == "2.1.0"
    assert "runs" in sarif and sarif["runs"]
    assert "results" in sarif["runs"][0]


def test_end_to_end_outputs_are_byte_deterministic(repo: Path, tmp_path: Path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _run_cli("ci-report", "--path", str(repo), "--fail-on", "never", "--format", "json", "--output", str(a))
    _run_cli("ci-report", "--path", str(repo), "--fail-on", "never", "--format", "json", "--output", str(b))
    assert a.read_bytes() == b.read_bytes()

    ca = tmp_path / "ca.md"
    cb = tmp_path / "cb.md"
    _run_cli("ci-report", "--path", str(repo), "--fail-on", "never", "--format", "markdown", "--output", str(ca))
    _run_cli("ci-report", "--path", str(repo), "--fail-on", "never", "--format", "markdown", "--output", str(cb))
    assert ca.read_bytes() == cb.read_bytes()


def test_ci_report_gate_failure_exit_code(repo: Path, tmp_path: Path):
    out = tmp_path / "r.json"
    rc = _run_cli(
        "ci-report", "--path", str(repo), "--min-score", "100",
        "--fail-on", "never", "--format", "json", "--output", str(out),
    )
    assert rc.returncode == 1
    # The report (with the failing gate) is still written for downstream steps.
    assert json.loads(out.read_text())["gate"]["pass"] is False
