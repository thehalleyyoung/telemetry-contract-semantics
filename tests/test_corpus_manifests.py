"""Structural validation of the shipped corpus manifests (offline, no network).

These assert that the committed, frozen corpus is well-formed: every subject is
pinned to a full 40-hex commit SHA, the curated corpus meets its size/host
target, and tier filtering yields a fast multi-host subset. No repository is
cloned, so this runs in the default offline suite and guards against a
malformed or shrunk manifest.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from telemetry_contracts.mining.corpus import load_corpus_manifest

_ROOT = Path(__file__).resolve().parents[1]
_CORPUS_DIR = _ROOT / "benchmarks" / "corpus"
_SHA = re.compile(r"^[0-9a-f]{40}$")

_MANIFESTS = sorted(p.name for p in _CORPUS_DIR.glob("*.json"))


@pytest.mark.parametrize("name", _MANIFESTS)
def test_manifest_is_well_formed(name):
    meta, subjects = load_corpus_manifest(_CORPUS_DIR / name)
    assert subjects, f"{name} has no subjects"
    seen = set()
    for s in subjects:
        assert _SHA.match(s.sha), f"{name}: {s.target} not pinned to a 40-hex SHA"
        assert s.host in {"github", "gitlab", "bitbucket", "codeberg"}
        key = (s.host, s.target)
        assert key not in seen, f"{name}: duplicate subject {key}"
        seen.add(key)
    # Selection protocol is recorded so the sample is inspectable.
    assert meta["criteria"]


def test_full_corpus_meets_size_and_host_target():
    _, subjects = load_corpus_manifest(_CORPUS_DIR / "corpus.json")
    assert len(subjects) >= 50, "curated corpus must hold >= 50 verified subjects"
    hosts = {s.host for s in subjects}
    assert len(hosts) >= 3, f"corpus must span >= 3 hosts, got {sorted(hosts)}"


def test_tier1_is_a_fast_multi_host_subset():
    _, subjects = load_corpus_manifest(_CORPUS_DIR / "corpus.json")
    tier1 = [s for s in subjects if s.tier == 1]
    assert 1 <= len(tier1) <= 10, "tier 1 should be a small, fast subset"
    assert {"github", "gitlab", "bitbucket"} <= {s.host for s in tier1}
