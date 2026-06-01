"""Network-gated proof that the corpus mining study works on real repositories.

Clones the frozen tier-1 corpus (GitHub/GitLab/Bitbucket repositories authored
without this tool in mind), each pinned to an exact commit SHA, runs the full
mining study, and asserts:

* every subject is cloned by its pinned SHA and scanned without crashing;
* the aggregate dataset is byte-for-byte deterministic across two runs;
* the headline statistic is internally consistent with the per-class prevalence;
* at least four subjects across at least three hosts are analyzed, with both
  telemetry-bearing and no-telemetry repositories exercised.

Skipped unless ``TELEMETRY_CONTRACTS_NETWORK_TESTS=1`` and ``git`` is on PATH.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from telemetry_contracts.bug_classes import HEADLINE_GAP
from telemetry_contracts.mining import load_corpus_manifest, mine_corpus

pytestmark = pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)

_MANIFEST = Path(__file__).resolve().parents[1] / "benchmarks" / "corpus" / "tier1.json"


@pytest.fixture(scope="module")
def dataset():
    _protocol, subjects = load_corpus_manifest(_MANIFEST)
    return mine_corpus(subjects)


def test_corpus_covers_four_repos_three_hosts(dataset):
    assert dataset["subjects_total"] >= 4
    assert len(dataset["hosts"]) >= 3
    # Both data-bearing and data-free subjects are present.
    assert dataset["subjects_with_telemetry"] >= 1
    assert dataset["subjects_with_telemetry"] < dataset["subjects_total"]
    assert not dataset.get("errors"), f"unexpected mining errors: {dataset.get('errors')}"


def test_dataset_is_deterministic_across_runs(dataset):
    _protocol, subjects = load_corpus_manifest(_MANIFEST)
    again = mine_corpus(subjects)
    # The 'errors' key may legitimately vary only if a host is transiently down;
    # compare the analytic core, which must be byte-identical.
    core_keys = ["headline", "bug_class_prevalence", "score_distribution", "subjects",
                 "subjects_total", "subjects_with_telemetry", "hosts", "events_total"]
    first = {k: dataset[k] for k in core_keys}
    second = {k: again[k] for k in core_keys}
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_headline_consistent_with_prevalence(dataset):
    headline = dataset["headline"]
    prevalence = dataset["bug_class_prevalence"][HEADLINE_GAP]
    # By construction the headline counts subjects with the correlation gap, so
    # its count must equal the per-class prevalence count. The headline's
    # share-of-telemetry uses the same (telemetry-bearing) denominator as
    # prevalence, so those permilles must match; the primary headline permille
    # uses the stricter failure-bearing denominator and is therefore >= it.
    assert headline["cannot_answer"] == prevalence["subjects_present"]
    assert headline["share_of_telemetry_permille"] == prevalence["subjects_present_permille"]
    assert headline["cannot_answer_permille"] >= headline["share_of_telemetry_permille"]
    assert 0 <= headline["cannot_answer_permille"] <= 1000


def test_pinned_shas_are_recorded_in_subjects(dataset):
    for row in dataset["subjects"]:
        assert len(row["sha"]) == 40
        if row["has_telemetry"]:
            assert row["diagnosability_score"] is not None
            assert 0 <= row["diagnosability_score"] <= 100
        else:
            assert row["diagnosability_score"] is None
