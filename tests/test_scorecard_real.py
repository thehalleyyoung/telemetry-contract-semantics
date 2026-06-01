"""Network-gated proof that the observability badge renders on real repos.

Clones the frozen tier-1 corpus (real GitHub/GitLab/Bitbucket repositories
authored without this tool in mind), produces a CI report for each via
``analyze_for_ci``, and renders the badge SVG, scorecard SVG, and shields.io
endpoint JSON from each, asserting they are well-formed, byte-deterministic, and
color-correct across >=4 real repos.

Skipped unless ``TELEMETRY_CONTRACTS_NETWORK_TESTS=1`` and ``git`` is on PATH.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import xml.dom.minidom as minidom
from pathlib import Path
from typing import Any

import pytest

from telemetry_contracts.github_action import analyze_for_ci
from telemetry_contracts.mining import load_corpus_manifest
from telemetry_contracts.mining.study import _clone_at_sha
from telemetry_contracts.repo_scan import parse_repo_target
from telemetry_contracts.scorecard import (
    render_badge_svg,
    render_scorecard_svg,
    score_color,
    shields_endpoint_json,
)

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
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-badge-")
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


def test_badges_are_well_formed_and_deterministic(reports):
    for target, report in sorted(reports.items()):
        score = report.get("diagnosability_score")
        svg = render_badge_svg(score)
        minidom.parseString(svg)  # well-formed XML
        assert svg == render_badge_svg(score), target  # byte-deterministic
        card = render_scorecard_svg(report)
        minidom.parseString(card)
        assert card == render_scorecard_svg(report), target


def test_shields_endpoint_matches_color_band(reports):
    for target, report in sorted(reports.items()):
        score = report.get("diagnosability_score")
        payload = shields_endpoint_json(score)
        assert payload["schemaVersion"] == 1
        assert payload["color"] == score_color(score), target
        if report["has_telemetry"]:
            assert payload["message"] == f"{score}/100"
        else:
            assert payload["message"] == "no telemetry"
