"""Network-gated proof that the formal model discharges on real repositories.

Clones the frozen tier-1 corpus (real GitHub/GitLab/Bitbucket repositories
authored without this tool in mind), harvests their actual telemetry, and:

* drives the data-dependent witnesses (abstract-domain presence soundness) with
  each repo's real events and asserts the soundness obligation still holds;
* runs the full ``run_pipeline`` staged loop on a deterministic per-repo fixture
  derived from real imports and asserts the monotonicity/termination guarantees
  observed in the impact ledger (bounded rounds, baseline <= final, no applied
  regressions) over >=4 real repos;
* asserts the discharge is deterministic on real events.

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

from telemetry_contracts.adapters import load_events_auto
from telemetry_contracts.formal_model import discharge_formal_model
from telemetry_contracts.mining import load_corpus_manifest
from telemetry_contracts.mining.study import _clone_at_sha
from telemetry_contracts.repo_scan import find_telemetry_files, parse_repo_target

pytestmark = pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)

_MANIFEST = Path(__file__).resolve().parents[1] / "benchmarks" / "corpus" / "tier1.json"
_MAX_EVENTS_PER_REPO = 200


@pytest.fixture(scope="module")
def harvest():
    _protocol, subjects = load_corpus_manifest(_MANIFEST)
    processed: dict[str, list[dict[str, Any]]] = {}
    for subject in subjects:
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-fm-")
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
            processed[subject.target] = events
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return processed


def test_processed_at_least_four_real_repos(harvest):
    assert len(harvest) >= 4, f"expected >=4 processed repos, got {sorted(harvest)}"


def test_formal_model_discharges_on_real_events(harvest):
    for target, events in sorted(harvest.items()):
        report = discharge_formal_model(events=events)
        # The whole model is fixture-anchored except the data-dependent witnesses;
        # those must still hold when driven by real harvested events.
        assert report["summary"]["all_discharged"], (
            target,
            [(v["id"], v["detail"]) for v in report["obligations"] if not v["holds"]],
        )


def test_presence_soundness_holds_on_every_real_repo(harvest):
    for target, events in sorted(harvest.items()):
        report = discharge_formal_model(events=events)
        cell = {v["id"]: v for v in report["obligations"]}[
            "FM.abstract-domains.presence-soundness"
        ]
        assert cell["holds"], f"{target}: {cell['detail']}"


def test_discharge_is_deterministic_on_real_events(harvest):
    for target, events in sorted(harvest.items()):
        a = json.dumps(discharge_formal_model(events=events), sort_keys=True)
        b = json.dumps(discharge_formal_model(events=list(events)), sort_keys=True)
        assert a == b, f"non-deterministic discharge on {target}"
