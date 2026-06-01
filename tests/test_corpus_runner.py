"""Offline end-to-end tests for the resumable, cached corpus runner.

A real local git checkout is laid out at the path the runner expects so the whole
cache + status + resume machinery is exercised without any network access.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from telemetry_contracts.mining.corpus import CorpusSubject
from telemetry_contracts.mining.runner import (
    StatusTable,
    run_corpus,
    subject_checkout_dir,
)


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e",
        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        "PATH": __import__("os").environ.get("PATH", ""),
    }
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True, env=env,
    )
    return out.stdout.strip()


@pytest.fixture()
def planted_subject(tmp_path):
    """Create a real git checkout with telemetry and return (subject, repos_dir)."""

    repos_dir = tmp_path / "_repos"
    subject = CorpusSubject(
        target="local/fixture", sha="0" * 40, host="github",
        license="MIT", rationale="fixture", tier=1,
    )
    checkout = subject_checkout_dir(repos_dir, subject)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    _git(checkout.parent, "init", "-q", checkout.name)
    logs = checkout / "logs"
    logs.mkdir()
    # Failure events with no correlation id -> "cannot answer why did this fail".
    (logs / "app.jsonl").write_text(
        "\n".join(
            json.dumps({"level": "error", "message": "boom", "status": "failed", "service": "api"})
            for _ in range(5)
        ) + "\n",
        encoding="utf-8",
    )
    _git(checkout, "add", "-A")
    _git(checkout, "commit", "-q", "-m", "telemetry")
    real_sha = _git(checkout, "rev-parse", "HEAD")
    # Move the checkout to the path keyed by the *real* sha.
    final = subject_checkout_dir(repos_dir, CorpusSubject(
        target=subject.target, sha=real_sha, host=subject.host,
        license=subject.license, rationale=subject.rationale, tier=subject.tier,
    ))
    checkout.rename(final)
    real_subject = CorpusSubject(
        target=subject.target, sha=real_sha, host=subject.host,
        license=subject.license, rationale=subject.rationale, tier=subject.tier,
    )
    return real_subject, repos_dir


def test_run_corpus_caches_and_is_byte_deterministic(planted_subject, tmp_path):
    subject, repos_dir = planted_subject
    cache_dir = tmp_path / "cache"

    sources_first: list[str] = []
    first = run_corpus(
        [subject], cache_dir=cache_dir, repos_dir=repos_dir,
        on_subject=lambda s, src, err: sources_first.append(src),
    )
    assert sources_first == ["fresh"]
    assert first["subjects_total"] == 1
    assert first["subjects_with_telemetry"] == 1

    sources_second: list[str] = []
    second = run_corpus(
        [subject], cache_dir=cache_dir, repos_dir=repos_dir,
        on_subject=lambda s, src, err: sources_second.append(src),
    )
    assert sources_second == ["cache"]
    assert first == second  # byte-identical whether fresh or cached


def test_status_table_records_progress_and_resumes(planted_subject, tmp_path):
    subject, repos_dir = planted_subject
    cache_dir = tmp_path / "cache"
    run_corpus([subject], cache_dir=cache_dir, repos_dir=repos_dir)

    status_path = cache_dir / "status.json"
    assert status_path.is_file()
    table = StatusTable(status_path)
    assert subject.identity in table.subjects
    entry = table.subjects[subject.identity]
    assert entry["status"] == "done"
    assert entry["source"] == "fresh"
    assert table.engine_fingerprint is not None


def test_cache_eviction_forces_recompute(planted_subject, tmp_path):
    subject, repos_dir = planted_subject
    cache_dir = tmp_path / "cache"
    run_corpus([subject], cache_dir=cache_dir, repos_dir=repos_dir)

    # Evict the single cached result; the next run must recompute it.
    for entry in (cache_dir / "results").glob("*.json"):
        entry.unlink()
    sources: list[str] = []
    run_corpus(
        [subject], cache_dir=cache_dir, repos_dir=repos_dir,
        on_subject=lambda s, src, err: sources.append(src),
    )
    assert sources == ["fresh"]


def test_run_corpus_records_clone_error_via_injected_failure(planted_subject, tmp_path, monkeypatch):
    # Force the clone path to fail deterministically (no network) and assert the
    # error is recorded without aborting the run.
    subject, repos_dir = planted_subject
    from telemetry_contracts.mining import runner as runner_mod
    from telemetry_contracts.repo_scan import RepoScanError

    def boom(*args, **kwargs):
        raise RepoScanError("synthetic clone failure")

    # Remove the planted checkout so the runner takes the clone path, then fail it.
    import shutil
    shutil.rmtree(subject_checkout_dir(repos_dir, subject))
    monkeypatch.setattr(runner_mod, "_clone_at_sha", boom)

    cache_dir = tmp_path / "cache"
    dataset = run_corpus([subject], cache_dir=cache_dir, repos_dir=repos_dir)
    assert dataset["subjects_total"] == 0
    assert len(dataset["errors"]) == 1
    assert "synthetic clone failure" in dataset["errors"][0]["error"]
    # The failure is reflected in the status table too.
    table = StatusTable(cache_dir / "status.json")
    assert table.subjects[subject.identity]["status"] == "error"
