"""Offline, deterministic tests for the four final roadmap capabilities:

* high-impact filter rubric (score_addition / score_code_proposal / feature_scorecard)
* reviewable companion patches generated against the cloned SHA (git apply --check)
* the progressive-depth ladder (correlation -> ordering -> temporal -> privacy)
* the post-hoc feature scorecard

A real ``git`` working tree is created with the git CLI (no network) so the
``git apply --check`` path and SHA-anchored patches are genuinely exercised.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from telemetry_contracts.code_proposals import (
    _build_patch,
    _slugify_gap,
    _unified_new_file_patch,
    generate_code_proposals,
)
from telemetry_contracts.high_impact_filter import (
    feature_scorecard,
    score_addition,
    score_code_proposal,
)
from telemetry_contracts.pipeline import (
    _data_got_richer,
    _depth_report,
    _depth_summary,
    instrumentation_plan,
    diagnose,
    MAX_DEPTH_TIER,
)


# --------------------------------------------------------------------------- #
# Item 002 — high-impact filter rubric
# --------------------------------------------------------------------------- #

def test_score_addition_fixed_point_and_verdict():
    s = score_addition(questions_unblocked=2, signals_introduced=1, edges_introduced=1,
                       lines_added=6, files_touched=1)
    # (2+1+1)*1000 // (6+1) == 571 -> high-impact, deterministic integer
    assert s["analytic_signal"] == 4
    assert s["surface_area"] == 7
    assert s["impact_milli"] == 571
    assert s["verdict"] == "high-impact"
    assert s["breakdown"]["questions_unblocked"] == 2


def test_score_addition_zero_surface_is_indeterminate_not_error():
    s = score_addition(questions_unblocked=3, signals_introduced=0, lines_added=0, files_touched=0)
    assert s["surface_area"] == 0
    assert s["impact_milli"] == 0
    assert s["verdict"] == "indeterminate-zero-surface"


def test_score_addition_low_impact_for_large_surface():
    s = score_addition(questions_unblocked=1, signals_introduced=0, lines_added=200, files_touched=5)
    assert s["verdict"] == "low-impact"


def test_score_code_proposal_is_deterministic():
    proposal = {
        "gap": "missing-correlation",
        "snippet": "from opentelemetry import trace\n\ndef annotate(operation, trace_id):\n    pass\n",
        "validation": {"present_in_source": ["trace_id"], "intended_names": ["trace_id"]},
        "questions_unblocked": ["Q1"],
        "patch": {"path": "telemetry_instrumentation/x.py", "added_lines": 9},
    }
    a = score_code_proposal(proposal)
    b = score_code_proposal(proposal)
    assert a == b
    assert a["breakdown"]["edges_introduced"] == 1  # correlation introduces an edge


# --------------------------------------------------------------------------- #
# Item 053 — reviewable companion patches against the cloned SHA
# --------------------------------------------------------------------------- #

def test_slugify_gap_is_path_safe():
    assert _slugify_gap("missing-correlation") == "missing-correlation"
    # traversal / separators / dots are all neutralized
    for hostile in ["../../etc/passwd", "a/b\\c", "..", "...", "  ", "WEIRD Name!!"]:
        slug = _slugify_gap(hostile)
        assert "/" not in slug and "\\" not in slug
        assert ".." not in slug
        assert slug == "" or slug[0] not in "-_."
        assert slug  # never empty


def test_unified_new_file_patch_is_canonical_and_lf_only():
    patch = _unified_new_file_patch("telemetry_instrumentation/x.py", "alpha\nbeta\n")
    assert patch.startswith("diff --git a/telemetry_instrumentation/x.py b/telemetry_instrumentation/x.py\n")
    assert "new file mode 100644\n" in patch
    assert "--- /dev/null\n" in patch
    assert "+++ b/telemetry_instrumentation/x.py\n" in patch
    assert "@@ -0,0 +1,2 @@\n" in patch
    assert "+alpha\n+beta\n" in patch
    assert "\r" not in patch  # LF only


def _git_init(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.email=a@b.c", "-c", "user.name=x",
                    "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.email=a@b.c", "-c", "user.name=x",
                    "commit", "-qm", "init"], check=True)


def test_build_patch_applies_clean_against_real_checkout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello\n")
    _git_init(repo)
    snippet = "import logging\n\nlogger = logging.getLogger('x')\n"
    patch = _build_patch(repo, "missing-correlation", snippet)
    assert patch["path"] == "telemetry_instrumentation/missing-correlation.py"
    assert patch["applies_clean"] is True
    assert patch["apply_reason"] == "applies-clean"
    assert patch["rewrites_business_logic"] is False
    # the patch really does apply (and we can confirm the file would appear)
    proc = subprocess.run(
        ["git", "-C", str(repo), "apply", "--check", "-"],
        input=patch["patch"], text=True, capture_output=True,
    )
    assert proc.returncode == 0


def test_build_patch_collision_gets_deterministic_suffix(tmp_path):
    repo = tmp_path / "repo"
    (repo / "telemetry_instrumentation").mkdir(parents=True)
    (repo / "telemetry_instrumentation" / "missing-correlation.py").write_text("# existing\n")
    (repo / "README.md").write_text("hi\n")
    _git_init(repo)
    snippet = "import logging\n"
    p1 = _build_patch(repo, "missing-correlation", snippet)
    p2 = _build_patch(repo, "missing-correlation", snippet)
    assert p1["path"] != "telemetry_instrumentation/missing-correlation.py"
    assert p1["path"] == p2["path"]  # deterministic suffix from content hash
    assert p1["applies_clean"] is True


def test_build_patch_without_git_is_unchecked():
    patch = _build_patch(None, "missing-duration", "x = 1\n")
    assert patch["applies_clean"] is None
    assert patch["apply_reason"] == "not-checked"
    assert patch["patch_sha256"]  # still deterministic content hash


def test_generate_proposals_carry_clean_patches_and_scores(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("x\n")
    _git_init(repo)
    diag = diagnose([
        {"kind": "event", "service": "api", "status": "error", "message": "boom"},
        {"kind": "event", "service": "api", "status": "ok"},
    ], service="api")
    plan = instrumentation_plan(diag, libraries=["opentelemetry"])
    result = generate_code_proposals(plan, libraries=["opentelemetry"], commit="deadbeef", repo_root=repo)
    assert result["proposals"]
    assert result["patches_all_apply_clean"] is True
    for p in result["proposals"]:
        assert p["patch"]["applies_clean"] is True
        assert p["impact_score"]["impact_milli"] >= 0
        assert p["applied_to_repo"] is False


# --------------------------------------------------------------------------- #
# Item 081 — progressive-depth ladder
# --------------------------------------------------------------------------- #

_DIAG = {"components": {"failures": 4, "failures_without_correlation": 1,
                        "spans": 2, "spans_without_duration": 0, "sensitive_values": 0}}
_BASE = {"order_inferred": True, "concurrency_pairs": 0,
         "inferred_ordering": {"support_full_groups": 3, "enforceable": True,
                               "steps": [{"kind": "log", "name": "a"}]}}


def test_depth_report_status_transitions():
    rpt = _depth_report(3, scheduled_tier=3, effective_tier=2, diag=_DIAG, base=_BASE)
    statuses = {t["name"]: t["status"] for t in rpt["tiers"]}
    assert statuses["correlation"] == "ran"
    assert statuses["ordering"] == "ran"
    assert statuses["temporal"] == "skipped_insufficient_data"  # scheduled but not unlocked
    assert statuses["privacy"] == "not_reached"                 # not scheduled yet
    assert rpt["deepest_check"] == "ordering"
    # ran tiers carry a metric; others don't
    for t in rpt["tiers"]:
        assert (t["metric"] is not None) == (t["status"] == "ran")


def test_depth_report_correlation_metric():
    rpt = _depth_report(1, 1, 1, _DIAG, _BASE)
    corr = rpt["tiers"][0]["metric"]
    assert corr["failures"] == 4 and corr["correlated_failures"] == 3
    assert corr["coverage_pct"] == 75


def test_data_got_richer_predicate():
    assert _data_got_richer({"new_signals": ["span:x"]}) is True
    assert _data_got_richer({"ordering_support_delta": 2}) is True
    assert _data_got_richer({"order_newly_inferred": True}) is True
    assert _data_got_richer({"new_signals": [], "ordering_support_delta": 0}) is False


def test_depth_summary_accounts_for_unreached_tiers():
    rounds = [{"depth": {"effective_tier": 2}}, {"depth": {"effective_tier": 1}}]
    summary = _depth_summary(rounds, "no measurable improvement from last round")
    assert summary["highest_tier_reached"] == 2
    assert summary["deepest_check_reached"] == "ordering"
    assert [t["name"] for t in summary["tiers_not_reached"]] == ["temporal", "privacy"]
    assert summary["not_reached_reason"]


def test_max_depth_tier_is_four():
    assert MAX_DEPTH_TIER == 4


# --------------------------------------------------------------------------- #
# Item 098 — post-hoc feature scorecard
# --------------------------------------------------------------------------- #

def test_feature_scorecard_isolated_vs_confounded():
    rounds = [
        {"round": 1, "plan": {"planned_changes": [{"gap": "missing-correlation"}]},
         "code_proposals": {"proposals": [{"impact_score": {"surface_area": 7}}]}},
        {"round": 2, "plan": {"planned_changes": [{"gap": "a"}, {"gap": "b"}]},
         "code_proposals": {"proposals": [{"impact_score": {"surface_area": 5}},
                                          {"impact_score": {"surface_area": 5}}]}},
    ]
    ledger = [
        {"round": 1, "predicted_score_points": 30, "realized_score_delta": 30, "changes_applied": 1, "quarantined": False},
        {"round": 2, "predicted_score_points": 20, "realized_score_delta": 0, "changes_applied": 2, "quarantined": False},
    ]
    card = feature_scorecard(rounds, ledger)
    assert card["is_repository_finding"] is False
    e1, e2 = card["entries"]
    assert e1["attribution"] == "isolated"
    assert e2["attribution"] == "confounded"
    assert e1["recommendation"] == "keep"
    # round 2 realized nothing -> recommended for prune handling (confounded keeps it honest)
    assert e2["recommendation"].startswith("keep") or e2["recommendation"].startswith("prune")


def test_feature_scorecard_skips_quarantined_rounds():
    rounds = [{"round": 1, "plan": {"planned_changes": [{"gap": "x"}]},
               "code_proposals": {"proposals": []}}]
    ledger = [{"round": 1, "predicted_score_points": 10, "realized_score_delta": 0,
               "changes_applied": 0, "quarantined": True}]
    card = feature_scorecard(rounds, ledger)
    assert card["entries"] == []
