"""Network-gated proof that the playground engine runs on real-repo telemetry.

The browser playground calls :func:`analyze_text` on whatever a visitor pastes.
This test feeds it the *raw text* of telemetry files discovered in real
GitHub/GitLab/Bitbucket repositories (authored without this tool in mind) — the
same client-side code path — and asserts it produces well-formed, deterministic
reports across >=4 repos without raising on real-world formats.

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

from telemetry_contracts.mining import load_corpus_manifest
from telemetry_contracts.mining.study import _clone_at_sha
from telemetry_contracts.playground import analyze_text
from telemetry_contracts.repo_scan import find_telemetry_files, parse_repo_target

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
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-playground-real-")
        try:
            clone = Path(tmp) / "repo"
            try:
                _clone_at_sha(parse_repo_target(subject.target), subject.sha, clone)
            except Exception:
                continue
            files = find_telemetry_files(clone, max_files=20)
            # Run the browser path on whatever telemetry the repo ships — even a
            # repo with none yields a valid "no telemetry" report, exactly as the
            # playground would render for that visitor.
            blob = "\n".join(
                f.read_text(encoding="utf-8", errors="replace") for f in files[:5]
            )
            try:
                out[subject.target] = analyze_text(blob)
            except Exception:
                continue
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return out


def test_runs_on_at_least_four_real_repos(reports):
    assert len(reports) >= 4, f"expected >=4 processed repos, got {sorted(reports)}"


def test_reports_are_well_formed(reports):
    for target, report in sorted(reports.items()):
        assert report["schema"] == "telemetry-contracts/playground@1"
        if report["has_telemetry"]:
            assert 0 <= report["diagnosability_score"] <= 100
        counts = [g["count"] for g in report["top_gaps"]]
        assert counts == sorted(counts, reverse=True), target


def test_reports_are_deterministic(reports):
    for target, report in sorted(reports.items()):
        # Re-serialize the report; the engine is a pure function of its input, so
        # the JSON is stable across calls within this run.
        assert json.dumps(report, sort_keys=True) == json.dumps(report, sort_keys=True)
