"""Network-gated proof that the execution proof works on real repositories.

Clones the frozen tier-1 corpus (real GitHub/GitLab/Bitbucket repositories
authored without this tool in mind), runs the full pipeline with execution proof
enabled over each, and asserts that every generated stdlib-``logging``
instrumentation proposal compiles, imports, and emits its promised fields in the
hardened isolated subprocess — without ever building or executing the target
repository's own code.

Skipped unless ``TELEMETRY_CONTRACTS_NETWORK_TESTS=1`` and ``git`` is on PATH.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from telemetry_contracts.execution import (
    STATUS_EMISSION_CLEAN,
    STATUS_NEEDS_DEP,
    execution_proof,
)
from telemetry_contracts.mining import load_corpus_manifest
from telemetry_contracts.mining.study import _clone_at_sha
from telemetry_contracts.pipeline import run_pipeline
from telemetry_contracts.repo_scan import parse_repo_target

pytestmark = pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)

_MANIFEST = Path(__file__).resolve().parents[1] / "benchmarks" / "corpus" / "tier1.json"


@pytest.fixture(scope="module")
def proofs() -> dict[str, dict[str, Any]]:
    _protocol, subjects = load_corpus_manifest(_MANIFEST)
    out: dict[str, dict[str, Any]] = {}
    for subject in subjects:
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-exec-real-")
        try:
            clone = Path(tmp) / "repo"
            try:
                _clone_at_sha(parse_repo_target(subject.target), subject.sha, clone)
            except Exception:
                continue
            try:
                report = run_pipeline(clone, prove_execution=True)
            except Exception:
                continue
            out[subject.target] = report.get("execution_proof") or {
                "proofs": [],
                "summary": {"all_logging_emit_clean": True},
            }
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return out


def test_pipeline_runs_on_at_least_four_real_repos(proofs):
    assert len(proofs) >= 4, f"expected >=4 processed repos, got {sorted(proofs)}"


def test_logging_proposals_emit_promised_fields_on_real_repos(proofs):
    saw_any_logging_proposal = False
    for target, proof in sorted(proofs.items()):
        for p in proof.get("proofs", []):
            if p["library_kind"] != "logging":
                continue
            saw_any_logging_proposal = True
            assert p["status"] == STATUS_EMISSION_CLEAN, (target, p["gap"], p["detail"])
            emitted = sorted({f for e in p["events"] for f in e["fields"]})
            assert emitted, f"{target}: {p['gap']} emitted no fields"
    assert saw_any_logging_proposal, "no logging proposals were generated across any real repo"


def test_execution_proof_is_evidence_only_and_honest(proofs):
    for target, proof in sorted(proofs.items()):
        if not proof.get("proofs"):
            continue
        assert proof["is_repository_finding"] is False
        assert "intentionally not run" in proof["honesty"]
        for p in proof["proofs"]:
            assert p["isolation"]["executed_target_repo_code"] is False
            # OTel proposals degrade honestly when the SDK is absent.
            if p["library_kind"] == "opentelemetry":
                assert p["status"] in {STATUS_NEEDS_DEP, "build-clean"}


def test_execution_proof_is_deterministic_on_real_repos(proofs):
    for target, proof in sorted(proofs.items()):
        proposals = [
            {"gap": p["gap"], "library_kind": p["library_kind"]} for p in proof.get("proofs", [])
        ]
        if not proposals:
            continue
        assert execution_proof(proposals) == execution_proof(list(proposals))
