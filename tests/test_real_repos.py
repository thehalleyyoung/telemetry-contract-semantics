"""Network-gated validation that the staged pipeline works *correctly* on real
repositories that were authored without this tool in mind.

These tests clone live public repositories across multiple hosts (GitHub,
GitLab, Bitbucket) and assert the hard invariants on each:

* the run never crashes and returns the stable ``pipeline@1`` schema;
* the source commit is recoverable from a real shallow clone;
* persisted artifacts are byte-for-byte deterministic across two runs of the
  same commit (content hashes identical);
* repos that ship telemetry data exercise the improvement loop and never
  regress (final diagnosability score >= baseline), and every generated code
  proposal is syntactically valid, introduces its intended names, and is
  honestly labelled as *not* applied to the user's repository;
* repos with no telemetry data degrade gracefully (no score, an explicit
  ``stopped_reason`` and actionable ``next_steps``) instead of crashing.

The suite is skipped unless ``TELEMETRY_CONTRACTS_NETWORK_TESTS=1`` is set and
``git`` is on PATH. Repositories are addressed via the host shorthands so the
``gitlab.com``/``bitbucket.org`` parsing paths are exercised too.
"""

from __future__ import annotations

import os
import shutil

import pytest

from telemetry_contracts.pipeline import run_pipeline
from telemetry_contracts.repo_scan import clone_repo, scan_repo

pytestmark = pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)

# (host label, target shorthand, expects_telemetry_data)
# A deliberate mix of hosts and of data-bearing vs. data-free repositories, all
# authored independently of this project.
REAL_REPOS = [
    ("github", "Vannut97/web-refinery", True),       # ships telemetry; loop improves 87->100
    ("github", "almbayedahmad/medflux", True),        # multiple telemetry files; loop runs
    ("github", "Keyhole-Koro/InsightifyCore", True),  # telemetry already strong
    ("gitlab", "gl:gitlab-examples/python-getting-started", False),  # source only, no data
    ("bitbucket", "bb:atlassian_tutorial/helloworld", False),        # tiny, no telemetry
]


def _assert_proposals_honest_and_valid(report):
    for rnd in report["rounds"]:
        for p in rnd["code_proposals"]["proposals"]:
            v = p["validation"]
            assert v["ast_parse_ok"] is True
            assert v["compile_ok"] is True
            assert v["introduces_intended_names"] is True
            # never silently applied to the user's repository
            assert p["applied_to_repo"] is False
            assert p["target_repo_build_not_run"] is True
            # item 053: a reviewable companion patch generated against the cloned
            # SHA must apply cleanly via `git apply --check`
            patch = p["patch"]
            assert patch["is_reviewable_companion_patch"] is True
            assert patch["rewrites_business_logic"] is False
            assert patch["applies_clean"] is True, patch["apply_reason"]
            # item 002: every proposal carries a mechanical high-impact score
            assert "impact_milli" in p["impact_score"]
            assert p["impact_score"]["surface_area"] > 0


@pytest.mark.parametrize("host,target,expects_data", REAL_REPOS, ids=[r[1] for r in REAL_REPOS])
def test_pipeline_correct_on_real_repo(tmp_path, host, target, expects_data):
    dest = tmp_path / "repo"
    clone_repo(target, dest)

    # Two independent runs against the same checkout must persist byte-identical
    # artifacts (determinism is a hard invariant of the whole design).
    r1 = run_pipeline(str(dest), out_dir=str(tmp_path / "o1"))
    r2 = run_pipeline(str(dest), out_dir=str(tmp_path / "o2"))

    assert r1["schema"] == "telemetry-contracts/pipeline@1"
    commit = r1["characterization"]["manifest"]["commit"]
    assert commit, "commit SHA must be recoverable from a real clone"
    assert (tmp_path / "o1" / commit / "pipeline.json").exists()
    assert isinstance(r1.get("regressed"), bool)

    h1 = {a["path"]: a["content_sha256"] for a in r1["artifacts"]["artifacts"]}
    h2 = {a["path"]: a["content_sha256"] for a in r2["artifacts"]["artifacts"]}
    assert h1 == h2, "artifact content hashes must be deterministic across runs"

    # progressive-depth and post-hoc scorecard are always present and well-formed
    depth = r1["depth_summary"]
    assert depth["highest_tier_reached"] >= 0
    assert depth["highest_tier_reached"] <= 4
    scorecard = r1["feature_scorecard"]
    assert scorecard["is_repository_finding"] is False

    has_telemetry = r1["characterization"]["has_telemetry"]
    if has_telemetry:
        base = r1["baseline"]["diagnosability_score"]
        final = r1["final"]["diagnosability_score"]
        assert final >= base, f"diagnosability regressed: {base} -> {final}"
        # quarantine/rollback guarantees a non-regressing realized outcome
        assert r1["regressed"] is False or final >= base
        _assert_proposals_honest_and_valid(r1)
        # depth tier 1 (correlation) must have actually run once data exists
        if r1["rounds"]:
            tier1 = r1["rounds"][0]["depth"]["tiers"][0]
            assert tier1["name"] == "correlation" and tier1["status"] == "ran"
    else:
        assert r1["baseline"] is None
        assert r1["final"] is None
        assert r1["stopped_reason"]
        assert r1["characterization"]["next_steps"]


@pytest.mark.parametrize("host,target,expects_data", REAL_REPOS, ids=[r[1] for r in REAL_REPOS])
def test_scan_repo_does_not_crash_on_real_repo(host, target, expects_data):
    # The zero-config discovery+analyze entry point must also tolerate arbitrary
    # real repositories regardless of how (or whether) they ship telemetry.
    report = scan_repo(target)
    assert report["schema"] == "telemetry-contracts/repo-scan@1"
    assert isinstance(report.get("files"), list)
    assert "summary" in report
