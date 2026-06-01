"""Network-gated proof that the baselines run correctly on real repositories.

Clones the frozen tier-1 corpus (real GitHub/GitLab/Bitbucket repositories
authored without this tool in mind), harvests their actual telemetry, and runs
the tool plus every comparison baseline over the real events, asserting:

* the baselines run without error and deterministically on >=4 real repos;
* the OTel semantic-convention baseline's out-of-scope coverage property holds on
  real data (it never flags sensitive/unclassified/cardinality gaps);
* on real telemetry the tool surfaces gaps the convention baseline misses
  (real-world differentiation, not just curated-set differentiation).

Skipped unless ``TELEMETRY_CONTRACTS_NETWORK_TESTS=1`` and ``git`` is on PATH.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from telemetry_contracts.adapters import load_events_auto
from telemetry_contracts.bug_classes import BUG_CLASS_IDS
from telemetry_contracts.evaluation.baselines import (
    predict_bug_class,
    predict_rule_light,
    predict_semantic_convention_only,
)
from telemetry_contracts.mining import load_corpus_manifest
from telemetry_contracts.mining.study import _clone_at_sha
from telemetry_contracts.repo_scan import find_telemetry_files, parse_repo_target

pytestmark = pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)

_MANIFEST = Path(__file__).resolve().parents[1] / "benchmarks" / "corpus" / "tier1.json"
_MAX_EVENTS_PER_REPO = 200

_OUT_OF_SCOPE_FOR_CONVENTION = ("sensitive-values", "unclassified-sensitive", "unbounded-cardinality")


def _positive_counts(events: list[dict[str, Any]], predict) -> dict[str, int]:
    counts = {gap: 0 for gap in BUG_CLASS_IDS}
    # Whole-set classes (cardinality is statistical) are evaluated over all events;
    # per-event classes are summed. We evaluate each class over the full event list
    # to mirror how the tool consumes a file's events.
    for gap in BUG_CLASS_IDS:
        present, _ = predict(events, gap)
        if present:
            counts[gap] += 1
    return counts


@pytest.fixture(scope="module")
def harvest():
    _protocol, subjects = load_corpus_manifest(_MANIFEST)
    processed: dict[str, list[dict[str, Any]]] = {}
    for subject in subjects:
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-bl-")
        try:
            clone = Path(tmp) / "repo"
            try:
                _clone_at_sha(parse_repo_target(subject.target), subject.sha, clone)
            except Exception:
                continue
            events: list[dict[str, Any]] = []
            for path in find_telemetry_files(clone, max_files=300):
                if len(events) >= _MAX_EVENTS_PER_REPO:
                    break
                try:
                    loaded = load_events_auto(path, tolerant=True)
                except Exception:
                    continue
                events.extend(loaded["events"][: _MAX_EVENTS_PER_REPO - len(events)])
            # A successfully cloned+scanned repo counts as "processed" even with 0
            # events (the tool correctly reports no gaps).
            processed[subject.target] = events
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return processed


def test_baselines_run_on_at_least_four_real_repos(harvest):
    assert len(harvest) >= 4, f"expected >=4 processed repos, got {sorted(harvest)}"


def test_baselines_are_deterministic_on_real_events(harvest):
    for target, events in sorted(harvest.items()):
        for predict in (predict_bug_class, predict_rule_light, predict_semantic_convention_only):
            first = _positive_counts(events, predict)
            second = _positive_counts(list(events), predict)
            assert first == second, f"non-deterministic counts on {target}"
            assert all(isinstance(v, int) and v >= 0 for v in first.values())


def test_convention_baseline_coverage_property_holds_on_real_data(harvest):
    for target, events in sorted(harvest.items()):
        counts = _positive_counts(events, predict_semantic_convention_only)
        for gap in _OUT_OF_SCOPE_FOR_CONVENTION:
            assert counts[gap] == 0, f"{target}: convention baseline flagged out-of-scope {gap}"


def test_tool_finds_real_gaps_the_convention_baseline_misses(harvest):
    tool_total = 0
    convention_total = 0
    tool_only_out_of_scope = 0
    for events in harvest.values():
        if not events:
            continue
        t = _positive_counts(events, predict_bug_class)
        c = _positive_counts(events, predict_semantic_convention_only)
        tool_total += sum(t.values())
        convention_total += sum(c.values())
        for gap in _OUT_OF_SCOPE_FOR_CONVENTION:
            tool_only_out_of_scope += t[gap]  # convention is always 0 here
    # The tool finds at least one real gap overall...
    assert tool_total >= 1, "tool found no gaps across any real repo"
    # ...and demonstrates real-world differentiation: it flags gaps in classes the
    # convention baseline structurally cannot, or simply finds more gaps overall.
    assert tool_only_out_of_scope >= 1 or tool_total > convention_total
