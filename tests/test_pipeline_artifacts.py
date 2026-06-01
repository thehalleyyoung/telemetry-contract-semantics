"""Tests for artifact persistence, code proposals, semantic differential, the
safety-gated quarantine/rollback loop, and the differential SARIF emitter.

All unit tests are offline and deterministic. A git working tree is created with
the real ``git`` CLI (no network) so commit-SHA-keyed artifacts are exercised.
The real-GitHub integration test is network-gated.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

import telemetry_contracts.pipeline as pipeline_mod
from telemetry_contracts.artifacts import (
    canonical_bytes,
    clone_cache_key,
    content_sha256,
    write_pipeline_artifacts,
)
from telemetry_contracts.code_proposals import generate_code_proposals, validate_proposal
from telemetry_contracts.pipeline import (
    baseline,
    collect_events,
    diagnose,
    instrumentation_plan,
    run_pipeline,
    semantic_differential,
    synthesize_instrumentation,
)
from telemetry_contracts.sarif import pipeline_differential_to_sarif
from telemetry_contracts.cli import main


def _write_repo(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    events = []
    for i in range(12):
        failure = i % 3 == 0
        event = {"kind": "span", "name": "http.request", "service": "api"}
        if failure:
            event["status"] = "error"
        else:
            event["trace_id"] = f"t{i}"
            event["duration_ms"] = 5 + i
        events.append(event)
    logs.joinpath("app.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    src.joinpath("app.py").write_text(
        "import logging\nfrom opentelemetry import trace\nfrom fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )
    return tmp_path


def _git_init(tmp_path):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True, env=env)


# --- baseline depth -------------------------------------------------------

def test_baseline_proof_obligations_and_ordering_evidence(tmp_path):
    _write_repo(tmp_path)
    events = collect_events(str(tmp_path))["events"]
    b = baseline(events, service="api")
    assert b["obligations_outstanding"] >= 1
    assert b["obligations_discharged"] + b["obligations_outstanding"] == len(b["proof_obligations"])
    # statuses are constrained
    assert all(o["status"] in {"discharged", "not_discharged"} for o in b["proof_obligations"])
    ev = b["ordering_evidence"]
    if not ev["order_inferred"]:
        assert ev["evidence_needed"]
    assert "concurrency_risk" in b


# --- semantic differential ------------------------------------------------

def test_semantic_differential_reports_new_signals(tmp_path):
    _write_repo(tmp_path)
    events = collect_events(str(tmp_path))["events"]
    before = baseline(events, service="api")
    plan = instrumentation_plan(diagnose(events, service="api"), max_changes=5)
    after_events = synthesize_instrumentation(events, plan)["events"]
    after = baseline(after_events, service="api")
    sem = semantic_differential(before, after)
    assert sem["schema"] == "telemetry-contracts/semantic-differential@1"
    assert sem["obligations_discharged_delta"] >= 0
    assert isinstance(sem["new_signals"], list)


# --- code proposals -------------------------------------------------------

def test_code_proposals_validate_and_introduce_names_otel(tmp_path):
    _write_repo(tmp_path)
    events = collect_events(str(tmp_path))["events"]
    plan = instrumentation_plan(diagnose(events, service="api"), libraries=["opentelemetry"], max_changes=5)
    proposals = generate_code_proposals(plan, libraries=["opentelemetry"], commit="abc")
    assert proposals["all_valid"] is True
    assert proposals["proposals"]
    for p in proposals["proposals"]:
        v = p["validation"]
        assert v["ast_parse_ok"] and v["compile_ok"]
        assert v["introduces_intended_names"] is True
        # the project's own static extractor confirms the names
        assert v["static_checker_detected_names"] == v["intended_names"]
        assert p["applied_to_repo"] is False
        assert p["target_repo_build_not_run"] is True


def test_code_proposals_logging_library_present_in_source():
    plan = {"planned_changes": [
        {"id": "chg-01-missing-correlation", "gap": "missing-correlation",
         "predicted_impact": {"events_affected": 1}},
    ]}
    proposals = generate_code_proposals(plan, libraries=["python-logging"], commit=None)
    p = proposals["proposals"][0]
    assert p["library_kind"] == "logging"
    assert p["validation"]["ast_parse_ok"] and p["validation"]["compile_ok"]
    assert "trace_id" in p["validation"]["present_in_source"]


def test_validate_proposal_rejects_broken_syntax():
    v = validate_proposal("def (:\n", ["trace_id"])
    assert v["ast_parse_ok"] is False


# --- artifact persistence -------------------------------------------------

def test_canonical_bytes_and_hash_are_stable():
    a = {"b": 1, "a": [3, 2, 1]}
    b = {"a": [3, 2, 1], "b": 1}
    assert canonical_bytes(a) == canonical_bytes(b)
    assert content_sha256(a) == content_sha256(b)


def test_clone_cache_key_is_stable():
    assert clone_cache_key("octocat/Hello-World", None) == clone_cache_key("octocat/Hello-World", "HEAD")
    assert clone_cache_key("a/b", "main") != clone_cache_key("a/b", "dev")


def test_artifacts_written_keyed_to_sha_and_deterministic(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_repo(repo)
    _git_init(repo)
    out1 = tmp_path / "o1"
    out2 = tmp_path / "o2"
    r1 = run_pipeline(str(repo), out_dir=str(out1))
    r2 = run_pipeline(str(repo), out_dir=str(out2))
    commit = r1["characterization"]["manifest"]["commit"]
    assert commit
    # artifacts are keyed under the commit SHA
    assert (out1 / commit / "index.json").exists()
    assert (out1 / commit / "characterization.json").exists()
    assert (out1 / commit / "rounds" / "round-001" / "code-proposals.json").exists()
    # content hashes identical across runs
    h1 = {a["path"]: a["content_sha256"] for a in r1["artifacts"]["artifacts"]}
    h2 = {a["path"]: a["content_sha256"] for a in r2["artifacts"]["artifacts"]}
    assert h1 == h2
    # persisted characterization drops the environment-specific root (portability)
    char = json.loads((out1 / commit / "characterization.json").read_text())["artifact"]
    assert char["manifest"]["root"] is None
    assert char["manifest"].get("root_normalized") is True


def test_artifacts_identical_across_clone_basenames(tmp_path):
    # Same content/commit reached via two differently-named working copies
    # (mimics temp clone "repo" vs content-addressed cache-dir key) must hash
    # identically once the env-specific root is normalized out.
    src = tmp_path / "repo"
    src.mkdir()
    _write_repo(src)
    _git_init(src)
    alt = tmp_path / "deadbeefcafebabe0"
    shutil.copytree(src, alt)
    r1 = run_pipeline(str(src), out_dir=str(tmp_path / "o1"))
    r2 = run_pipeline(str(alt), out_dir=str(tmp_path / "o2"))
    assert r1["characterization"]["manifest"]["commit"] == r2["characterization"]["manifest"]["commit"]
    h1 = {a["path"]: a["content_sha256"] for a in r1["artifacts"]["artifacts"]}
    h2 = {a["path"]: a["content_sha256"] for a in r2["artifacts"]["artifacts"]}
    assert h1 == h2


def test_write_pipeline_artifacts_provenance(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_repo(repo)
    report = run_pipeline(str(repo))
    index = write_pipeline_artifacts(report, tmp_path / "out", options={"rounds": 3})
    assert index["schema"] == "telemetry-contracts/artifact-index@1"
    sample = tmp_path / "out" / index["sha_key"] / "pipeline.json"
    wrapped = json.loads(sample.read_text())
    assert wrapped["provenance"]["stage"] == "pipeline"
    assert wrapped["provenance"]["generator"] == "telemetry-contracts/pipeline@1"
    assert wrapped["provenance"]["pipeline_options"] == {"rounds": 3}


# --- quarantine / rollback safety gate ------------------------------------

def test_pipeline_quarantines_regressing_round(tmp_path, monkeypatch):
    _write_repo(tmp_path)
    real = pipeline_mod.synthesize_instrumentation

    def poisoned(events, plan):
        out = real(events, plan)
        # inject a NEW privacy finding so the round regresses safety
        injected = dict(out["events"][0])
        injected["email"] = "leak@example.com"
        out["events"] = [injected, *out["events"][1:]]
        return out

    monkeypatch.setattr(pipeline_mod, "synthesize_instrumentation", poisoned)
    report = run_pipeline(str(tmp_path))
    assert report["regressed"] is True
    assert report["rounds"]
    assert any(r["quarantined"] for r in report["rounds"])
    # a quarantined round contributes zero realized impact (rolled back)
    for entry, rnd in zip(report["impact_ledger"], report["rounds"]):
        if rnd["quarantined"]:
            assert entry["realized_score_delta"] == 0
            assert entry["changes_applied"] == 0
    # the loop still terminates rather than retrying the same gaps forever
    assert "safety-approved" in report["stopped_reason"] or report["stopped_reason"] == "rounds exhausted"


def test_application_manifest_marks_status(tmp_path):
    events = [
        {"kind": "log", "name": "login", "service": "api", "email": "jane@example.com"},
        {"kind": "span", "name": "op", "service": "api", "status": "error"},
    ]
    report = run_pipeline_on_events(tmp_path, events)
    if report["rounds"]:
        manifest = report["rounds"][0]["application_manifest"]
        assert manifest["applied_to_repo"] is False
        assert manifest["target_repo_build_not_run"] is True
        statuses = {c["status"] for c in manifest["changes"]}
        # privacy change is deferred, never auto-applied
        assert "deferred_privacy" in statuses


def run_pipeline_on_events(tmp_path, events):
    logs = tmp_path / "logs"
    logs.mkdir()
    logs.joinpath("e.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    return run_pipeline(str(tmp_path))


# --- SARIF differential + CLI gating --------------------------------------

def test_pipeline_differential_sarif_namespace(tmp_path):
    _write_repo(tmp_path)
    report = run_pipeline(str(tmp_path))
    sarif = pipeline_differential_to_sarif(report)
    assert sarif["version"] == "2.1.0"
    rule_ids = {r["id"] for r in sarif["runs"][0]["tool"]["driver"]["rules"]}
    # all differential rules live in the dedicated namespace
    assert all(rid.startswith("pipeline.diff.") for rid in rule_ids)


def test_cli_pipeline_sarif_and_out_dir(tmp_path, capsys):
    _write_repo(tmp_path)
    out = tmp_path / "artifacts"
    code = main(["pipeline", "--path", str(tmp_path), "--format", "sarif", "--out-dir", str(out)])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["runs"][0]["tool"]["driver"]["name"] == "telemetry-contracts"
    assert list(out.iterdir())  # artifacts were written


def test_cli_pipeline_fail_on_regression(tmp_path, monkeypatch, capsys):
    _write_repo(tmp_path)
    real = pipeline_mod.synthesize_instrumentation

    def poisoned(events, plan):
        out = real(events, plan)
        injected = dict(out["events"][0])
        injected["email"] = "leak@example.com"
        out["events"] = [injected, *out["events"][1:]]
        return out

    monkeypatch.setattr(pipeline_mod, "synthesize_instrumentation", poisoned)
    code = main(["pipeline", "--path", str(tmp_path), "--format", "json", "--fail-on-regression"])
    capsys.readouterr()
    assert code == 1


# --- real GitHub repo (network-gated) -------------------------------------

@pytest.mark.skipif(
    os.environ.get("TELEMETRY_CONTRACTS_NETWORK_TESTS") != "1" or shutil.which("git") is None,
    reason="network/real-repo test; set TELEMETRY_CONTRACTS_NETWORK_TESTS=1 to enable",
)
def test_artifacts_and_proposals_on_real_github_repo(tmp_path):
    from telemetry_contracts.repo_scan import clone_repo

    dest = tmp_path / "repo"
    clone_repo("Vannut97/web-refinery", dest)
    out = tmp_path / "artifacts"
    report = run_pipeline(str(dest), out_dir=str(out))
    commit = report["characterization"]["manifest"]["commit"]
    assert commit
    assert (out / commit / "pipeline.json").exists()
    # every generated code proposal for the real repo must validate
    for rnd in report["rounds"]:
        proposals = rnd["code_proposals"]["proposals"]
        for p in proposals:
            assert p["validation"]["ast_parse_ok"] and p["validation"]["compile_ok"]
            assert p["validation"]["introduces_intended_names"] is True
