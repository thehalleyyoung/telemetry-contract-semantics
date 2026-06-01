"""Network-gated proof that the precision/recall machinery works on real events.

Clones the frozen tier-1 corpus (real GitHub/GitLab/Bitbucket repositories
authored without this tool in mind), harvests their actual telemetry events,
derives *objective* ground-truth labels for the two field-decidable bug classes
(missing-correlation, missing-duration) with an independent oracle, then runs the
shipped predictor over those real events and asserts:

* real telemetry is harvested from multiple independent repositories;
* on real data the predictor agrees exactly with the independent oracle for the
  field-decidable classes (no wiring drift between the scorer and the engine);
* the scorer produces a deterministic dataset over the real-derived gold set.

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
from telemetry_contracts.evaluation import (
    GoldItem,
    predict_bug_class,
    score_gold_set,
)
from telemetry_contracts.mining import load_corpus_manifest
from telemetry_contracts.mining.study import _clone_at_sha
from telemetry_contracts.repo_scan import find_telemetry_files, parse_repo_target

pytestmark = pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)

_MANIFEST = Path(__file__).resolve().parents[1] / "benchmarks" / "corpus" / "tier1.json"

# Independent oracle key sets (mirror the documented canonical fields; kept
# separate from the engine so agreement is a genuine cross-check).
_CORRELATION_KEYS = {
    "trace_id", "traceid", "trace.id", "request_id", "requestid",
    "span_id", "spanid", "correlation_id", "correlationid",
}
_DURATION_KEYS = {"duration_ms", "duration", "latency_ms", "latency", "elapsed_ms", "elapsed"}
_FAILURE_SEVERITIES = {"error", "critical", "fatal"}

_MAX_EVENTS_PER_REPO = 200


def _flat_keys(event: dict[str, Any]) -> set[str]:
    keys = {str(k).lower() for k in event.keys()}
    for container in ("attributes", "tags", "fields"):
        sub = event.get(container)
        if isinstance(sub, dict):
            keys |= {str(k).lower() for k in sub.keys()}
    return keys


def _oracle_is_failure(event: dict[str, Any]) -> bool:
    sev = str(event.get("severity", "")).lower()
    return sev in _FAILURE_SEVERITIES


def _oracle_missing_correlation(event: dict[str, Any]) -> bool | None:
    if not _oracle_is_failure(event):
        return None  # not an instance of this class
    return not (_flat_keys(event) & _CORRELATION_KEYS)


def _oracle_missing_duration(event: dict[str, Any]) -> bool | None:
    if str(event.get("kind", "event")).lower() not in {"span", "spans"}:
        return None
    return not (_flat_keys(event) & _DURATION_KEYS)


@pytest.fixture(scope="module")
def harvest():
    """Clone the corpus and harvest real events per repository."""
    _protocol, subjects = load_corpus_manifest(_MANIFEST)
    per_repo: dict[str, list[dict[str, Any]]] = {}
    for subject in subjects:
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-gt-")
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
            if events:
                per_repo[subject.target] = events
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return per_repo


def test_harvested_from_multiple_real_repos(harvest):
    assert len(harvest) >= 3, f"expected telemetry from >=3 repos, got {sorted(harvest)}"
    assert sum(len(v) for v in harvest.values()) >= 10


def test_predictor_matches_independent_oracle_on_real_events(harvest):
    checked = 0
    for target, events in sorted(harvest.items()):
        for idx, event in enumerate(events):
            for bug_class, oracle in (
                ("missing-correlation", _oracle_missing_correlation(event)),
                ("missing-duration", _oracle_missing_duration(event)),
            ):
                if oracle is None:
                    continue
                predicted, _ = predict_bug_class([event], bug_class)
                assert predicted == oracle, (
                    f"{target}[{idx}] {bug_class}: predictor={predicted} oracle={oracle} "
                    f"event={json.dumps(event, sort_keys=True)[:200]}"
                )
                checked += 1
    assert checked >= 1, "no field-decidable instances were harvested from real repos"


def test_scorer_runs_deterministically_on_real_gold(harvest):
    items: list[GoldItem] = []
    for target, events in sorted(harvest.items()):
        for idx, event in enumerate(events):
            mc = _oracle_missing_correlation(event)
            if mc is not None:
                items.append(GoldItem(
                    f"{target}#{idx}#mc", "missing-correlation", mc, [event],
                    "objective oracle label on real harvested event",
                    source={"subject": target},
                ))
            md = _oracle_missing_duration(event)
            if md is not None:
                items.append(GoldItem(
                    f"{target}#{idx}#md", "missing-duration", md, [event],
                    "objective oracle label on real harvested event",
                    source={"subject": target},
                ))
    assert items, "no real-derived gold items"
    a = score_gold_set(items)
    b = score_gold_set(list(reversed(items)))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    # On objectively-labeled real events the field-decidable classes are perfect.
    for gap in ("missing-correlation", "missing-duration"):
        m = a["per_class"][gap]
        if m["tp"] + m["fp"] + m["fn"] + m["tn"] > 0:
            assert m["f1_permille"] in (None, 1000) or (m["fp"] == 0 and m["fn"] == 0)
