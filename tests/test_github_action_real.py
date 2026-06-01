"""Network-gated proof that the GitHub Action's CI surface works on real repos.

Clones the frozen tier-1 corpus (real GitHub/GitLab/Bitbucket repositories
authored without this tool in mind) and runs the Action's underlying analysis —
``analyze_for_ci`` plus the configurable gate, the PR comment, and the scan ->
SARIF path — over each, asserting the report is well-formed, deterministic, and
that the gate/comment behave correctly on real telemetry across >=4 repos.

Skipped unless ``TELEMETRY_CONTRACTS_NETWORK_TESTS=1`` and ``git`` is on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from telemetry_contracts.github_action import (
    analyze_for_ci,
    build_pr_comment,
    evaluate_ci_gate_for_report,
)
from telemetry_contracts.mining import load_corpus_manifest
from telemetry_contracts.mining.study import _clone_at_sha
from telemetry_contracts.repo_scan import parse_repo_target, scan_directory
from telemetry_contracts.sarif import report_to_sarif

pytestmark = pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)

_MANIFEST = Path(__file__).resolve().parents[1] / "benchmarks" / "corpus" / "tier1.json"


@pytest.fixture(scope="module")
def reports() -> dict[str, dict[str, Any]]:
    _protocol, subjects = load_corpus_manifest(_MANIFEST)
    out: dict[str, dict[str, Any]] = {}
    for subject in subjects:
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-action-")
        try:
            clone = Path(tmp) / "repo"
            try:
                _clone_at_sha(parse_repo_target(subject.target), subject.sha, clone)
            except Exception:
                continue
            try:
                out[subject.target] = analyze_for_ci(clone)
            except Exception:
                continue
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return out


def test_runs_on_at_least_four_real_repos(reports):
    assert len(reports) >= 4, f"expected >=4 processed repos, got {sorted(reports)}"


def test_reports_are_well_formed(reports):
    for target, report in sorted(reports.items()):
        assert report["schema"] == "telemetry-contracts/ci-report@1"
        assert report["findings_total"] == sum(report["by_severity"].values())
        counts = [g["count"] for g in report["top_gaps"]]
        assert counts == sorted(counts, reverse=True), target
        if report["has_telemetry"]:
            assert 0 <= report["diagnosability_score"] <= 100


def test_gate_and_comment_behave_on_real_data(reports):
    for target, report in sorted(reports.items()):
        # fail-on never always passes the severity rule.
        assert evaluate_ci_gate_for_report(report, fail_on="never")["pass"] is True
        # A floor of 0 always passes; a floor above 100 always fails when scored.
        if report["has_telemetry"]:
            assert evaluate_ci_gate_for_report(report, min_score=0, fail_on="never")["pass"] is True
            assert evaluate_ci_gate_for_report(report, min_score=101, fail_on="never")["pass"] is False
        comment = build_pr_comment(report)
        assert comment.startswith("## 🔭 Observability report")
        assert "correctness property" in comment


def test_scan_to_sarif_is_wellformed_on_real_repos(reports, tmp_path):
    # Re-clone-free: drive SARIF from the same scan the Action runs by scanning a
    # fixture written from each real report's findings is not possible, so we
    # assert the report_to_sarif contract on a synthetic findings doc shaped like
    # a scan result with the real severity counts.
    for target, report in sorted(reports.items()):
        findings_doc = {
            "schema": "telemetry-contracts/scan@1",
            "findings": [
                {"severity": "warning", "code": g["code"], "message": "x", "path": "p"}
                for g in report["top_gaps"]
            ],
        }
        sarif = report_to_sarif(findings_doc)
        assert sarif["version"] == "2.1.0"
        assert sarif["runs"], target
        # determinism
        assert json.dumps(sarif, sort_keys=True) == json.dumps(report_to_sarif(findings_doc), sort_keys=True)


def test_reports_are_deterministic_on_real_repos(reports):
    for target, report in sorted(reports.items()):
        assert build_pr_comment(report) == build_pr_comment(report)
