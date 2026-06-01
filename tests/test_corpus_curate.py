"""Offline tests for the corpus curation helper.

The network/git clone step is injected, so these exercise the deterministic
pieces — host inference, manifest assembly (dedup + sort), and the
clone -> pin-real-SHA -> verify-telemetry reduction — against a real local git
checkout without any network access.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from telemetry_contracts.mining.curate import (
    build_manifest,
    candidate_subject,
    curate_corpus,
    infer_host,
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


def _make_repo(parent: Path, name: str, *, with_telemetry: bool) -> str:
    """Create a real git repo and return its full HEAD sha."""
    repo = parent / name
    repo.mkdir(parents=True)
    _git(parent, "init", "-q", name)
    if with_telemetry:
        logs = repo / "logs"
        logs.mkdir()
        (logs / "app.jsonl").write_text(
            "\n".join(
                json.dumps({"level": "error", "message": "boom",
                            "status": "failed", "service": "api"})
                for _ in range(4)
            ) + "\n",
            encoding="utf-8",
        )
    else:
        (repo / "README.md").write_text("# no telemetry here\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return _git(repo, "rev-parse", "HEAD")


def test_infer_host_recognizes_prefixes_and_domains():
    assert infer_host("owner/repo") == "github"
    assert infer_host("gl:group/proj") == "gitlab"
    assert infer_host("bb:team/repo") == "bitbucket"
    assert infer_host("https://gitlab.com/group/proj") == "gitlab"
    assert infer_host("https://bitbucket.org/team/repo.git") == "bitbucket"
    assert infer_host("https://codeberg.org/u/r") == "codeberg"


def test_candidate_subject_pins_real_sha_and_keeps_telemetry(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    real_sha = _make_repo(src, "fixture", with_telemetry=True)

    work = tmp_path / "_curate"

    def fake_clone(target, dest, *, depth=1):
        # Simulate a clone by copying the prepared checkout into place.
        import shutil
        shutil.copytree(src / "fixture", dest)

    subject = candidate_subject(
        "owner/fixture", work_dir=work, clone=fake_clone,
    )
    assert subject is not None
    assert subject["sha"] == real_sha
    assert subject["host"] == "github"
    assert subject["tier"] == 2
    assert subject["_facts"]["has_telemetry"] is True
    assert subject["_facts"]["event_count"] > 0
    assert "ships parseable telemetry" in subject["rationale"]


def test_candidate_subject_drops_repo_without_telemetry(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _make_repo(src, "bare", with_telemetry=False)

    def fake_clone(target, dest, *, depth=1):
        import shutil
        shutil.copytree(src / "bare", dest)

    assert candidate_subject(
        "owner/bare", work_dir=tmp_path / "_c", clone=fake_clone,
    ) is None
    # ...unless we explicitly allow no-telemetry graceful samples.
    kept = candidate_subject(
        "owner/bare", work_dir=tmp_path / "_c2", clone=fake_clone,
        require_telemetry=False,
    )
    assert kept is not None
    assert kept["_facts"]["has_telemetry"] is False


def test_candidate_subject_returns_none_on_clone_failure(tmp_path):
    from telemetry_contracts.repo_scan import RepoScanError

    def boom(target, dest, *, depth=1):
        raise RepoScanError("synthetic clone failure")

    assert candidate_subject(
        "owner/missing", work_dir=tmp_path / "_c", clone=boom,
    ) is None


def test_build_manifest_dedups_and_sorts():
    subjects = [
        {"target": "o/b", "sha": "b" * 40, "host": "github", "tier": 2},
        {"target": "o/a", "sha": "a" * 40, "host": "github", "tier": 2},
        {"target": "o/b", "sha": "b" * 40, "host": "github", "tier": 2},  # dup
        {"target": "g/x", "sha": "c" * 40, "host": "gitlab", "tier": 2},
    ]
    manifest = build_manifest(subjects, description="d", tier_note="n")
    targets = [(s["host"], s["target"]) for s in manifest["subjects"]]
    assert targets == [("github", "o/a"), ("github", "o/b"), ("gitlab", "g/x")]
    assert manifest["schema"] == "telemetry-contracts/corpus@1"
    assert manifest["selection_protocol"]["notes"] == "n"
    # Subjects carry only manifest fields (no internal facts leak into the file).
    assert set(manifest["subjects"][0]) == {"target", "sha", "host", "license", "rationale", "tier"}


def test_curate_corpus_respects_limit(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    shas = {name: _make_repo(src, name, with_telemetry=True) for name in ("r1", "r2", "r3")}

    def fake_clone(target, dest, *, depth=1):
        import shutil
        name = target.split("/")[-1]
        shutil.copytree(src / name, dest)

    kept = curate_corpus(
        ["o/r1", "o/r2", "o/r3"], work_dir=tmp_path / "_c",
        limit=2, clone=fake_clone,
    )
    assert len(kept) == 2
    assert kept[0]["sha"] == shas["r1"]
