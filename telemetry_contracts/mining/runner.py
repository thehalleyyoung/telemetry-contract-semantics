"""Resumable, crash-safe, content-addressed corpus runner (pure stdlib).

This turns the one-shot :func:`telemetry_contracts.mining.study.mine_corpus` into
a runner that can study a 300-subject corpus, stop, and continue deterministically:

* **Persistent, gitignored checkouts.** Each subject is cloned at its pinned SHA
  into a content-addressed directory under ``_repos/`` and re-used on the next
  run (verified with ``git rev-parse HEAD``), so re-running never re-downloads.
* **Content-addressed result cache.** A subject whose pinned commit *and* engine
  fingerprint are unchanged is a cache hit and is never re-analysed
  (see :mod:`telemetry_contracts.mining.cache`).
* **Crash-safe per-subject status table.** ``status.json`` is rewritten
  atomically after every subject, so a crashed run leaves a consistent record and
  the next run resumes from the cache.

The downloaded repositories and the cache are disposable derived artifacts and
are git-ignored; the manifest remains the single source of truth.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from ..repo_scan import RepoScanError, parse_repo_target
from .cache import ResultCache, atomic_write_json, engine_fingerprint, options_fingerprint
from .corpus import CorpusSubject
from .study import (
    aggregate,
    analyze_checkout,
    record_from_facts,
    scan_options,
)
from .study import _clone_at_sha  # shared clone-at-SHA helper

STATUS_SCHEMA = "telemetry-contracts/corpus-status@1"
DEFAULT_REPOS_DIRNAME = "_repos"
DEFAULT_CACHE_DIRNAME = ".cache"

OnSubject = Callable[[CorpusSubject, str, str | None], None] | None


def _safe_target(target: str) -> str:
    return target.replace("://", "_").replace("/", "__").replace(":", "_")


def subject_checkout_dir(repos_dir: Path, subject: CorpusSubject) -> Path:
    """Deterministic, collision-resistant checkout path for a subject."""

    return Path(repos_dir) / subject.host / f"{_safe_target(subject.target)}@{subject.sha[:12]}"


def _head_sha(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def download_subject(subject: CorpusSubject, repos_dir: str | Path, *, timeout: int = 300) -> Path:
    """Clone ``subject`` at its pinned SHA into ``repos_dir`` (idempotent).

    Re-uses an existing checkout iff ``git rev-parse HEAD`` already equals the
    pinned SHA; otherwise (re)clones. Always verifies the SHA after cloning.
    """

    dest = subject_checkout_dir(Path(repos_dir), subject)
    if dest.is_dir() and _head_sha(dest) == subject.sha:
        return dest
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    _clone_at_sha(parse_repo_target(subject.target), subject.sha, dest, timeout=timeout)
    head = _head_sha(dest)
    if head != subject.sha:
        raise RepoScanError(
            f"checkout of {subject.target} is at {head!r}, expected {subject.sha}"
        )
    return dest


def download_corpus(
    subjects: list[CorpusSubject],
    repos_dir: str | Path,
    *,
    timeout: int = 300,
    on_subject: OnSubject = None,
) -> dict[str, Any]:
    """Download every subject into ``repos_dir`` and report success/failure."""

    downloaded: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for subject in subjects:
        try:
            dest = download_subject(subject, repos_dir, timeout=timeout)
            downloaded.append({"target": subject.target, "sha": subject.sha, "path": str(dest)})
            if on_subject is not None:
                on_subject(subject, "downloaded", None)
        except RepoScanError as exc:
            errors.append({"target": subject.target, "sha": subject.sha, "error": str(exc)})
            if on_subject is not None:
                on_subject(subject, "error", str(exc))
    return {
        "schema": "telemetry-contracts/corpus-download@1",
        "repos_dir": str(repos_dir),
        "downloaded": sorted(downloaded, key=lambda d: (d["target"], d["sha"])),
        "errors": sorted(errors, key=lambda e: (e["target"], e["sha"])),
        "summary": {"requested": len(subjects), "downloaded": len(downloaded), "errors": len(errors)},
    }


class StatusTable:
    """A crash-safe, per-subject status table persisted atomically to JSON."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.subjects: dict[str, dict[str, Any]] = {}
        self.engine_fingerprint: str | None = None
        self.options_fingerprint: str | None = None
        if self.path.is_file():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.subjects = dict(data.get("subjects", {}))
                    self.engine_fingerprint = data.get("engine_fingerprint")
                    self.options_fingerprint = data.get("options_fingerprint")
            except (OSError, ValueError):
                self.subjects = {}

    def update(self, subject: CorpusSubject, status: str, *, source: str,
               error: str | None = None) -> None:
        self.subjects[subject.identity] = {
            "target": subject.target,
            "sha": subject.sha,
            "tier": subject.tier,
            "status": status,
            "source": source,
            "error": error,
        }
        self.flush()

    def flush(self) -> None:
        atomic_write_json(self.path, {
            "schema": STATUS_SCHEMA,
            "engine_fingerprint": self.engine_fingerprint,
            "options_fingerprint": self.options_fingerprint,
            "subjects": dict(sorted(self.subjects.items())),
        })


def verify_corpus(
    subjects: list[CorpusSubject],
    *,
    timeout: int = 300,
    on_subject: OnSubject = None,
) -> dict[str, Any]:
    """Verify each subject's pinned SHA actually resolves (clones into a temp dir).

    Network-bound. Confirms ``git rev-parse HEAD`` equals the pinned SHA for every
    subject, so a manifest can be proven replayable without keeping the checkouts.
    """

    ok: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for subject in subjects:
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-verify-")
        try:
            clone_dir = Path(tmp) / "repo"
            _clone_at_sha(parse_repo_target(subject.target), subject.sha, clone_dir)
            head = _head_sha(clone_dir)
            if head == subject.sha:
                ok.append({"target": subject.target, "sha": subject.sha})
                if on_subject is not None:
                    on_subject(subject, "ok", None)
            else:
                err = {"target": subject.target, "sha": subject.sha, "error": f"HEAD is {head!r}"}
                errors.append(err)
                if on_subject is not None:
                    on_subject(subject, "error", err["error"])
        except RepoScanError as exc:
            errors.append({"target": subject.target, "sha": subject.sha, "error": str(exc)})
            if on_subject is not None:
                on_subject(subject, "error", str(exc))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return {
        "schema": "telemetry-contracts/corpus-verify@1",
        "ok": sorted(ok, key=lambda d: (d["target"], d["sha"])),
        "errors": sorted(errors, key=lambda e: (e["target"], e["sha"])),
        "summary": {"requested": len(subjects), "ok": len(ok), "errors": len(errors)},
    }


def run_corpus(
    subjects: list[CorpusSubject],
    *,
    cache_dir: str | Path,
    repos_dir: str | Path | None = None,
    service: str | None = None,
    max_files: int = 300,
    max_events_per_file: int = 50_000,
    max_total_events: int = 200_000,
    on_subject: OnSubject = None,
) -> dict[str, Any]:
    """Study every subject incrementally and return the deterministic dataset.

    Cache hits (unchanged pinned commit + engine + options) are reused and never
    re-cloned or re-analysed. When ``repos_dir`` is given, checkouts are persisted
    there for reuse; otherwise each subject is cloned into a temp dir and removed.
    A crash at any point leaves a consistent status table and a populated cache,
    so the next invocation resumes deterministically.
    """

    options = scan_options(
        service=service, max_files=max_files,
        max_events_per_file=max_events_per_file, max_total_events=max_total_events,
    )
    engine_fp = engine_fingerprint()
    options_fp = options_fingerprint(options)
    cache = ResultCache(cache_dir, engine_fp=engine_fp, options=options)
    status = StatusTable(Path(cache_dir) / "status.json")
    status.engine_fingerprint = engine_fp
    status.options_fingerprint = options_fp

    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for subject in subjects:
        cached = cache.get(subject.sha)
        if cached is not None:
            records.append(record_from_facts(subject, cached))
            status.update(subject, "done", source="cache")
            if on_subject is not None:
                on_subject(subject, "cache", None)
            continue

        tmp: str | None = None
        try:
            if repos_dir is not None:
                clone_dir = download_subject(subject, repos_dir)
            else:
                tmp = tempfile.mkdtemp(prefix="telemetry-contracts-run-")
                clone_dir = Path(tmp) / "repo"
                _clone_at_sha(parse_repo_target(subject.target), subject.sha, clone_dir)
            facts = analyze_checkout(
                clone_dir, service=service, max_files=max_files,
                max_events_per_file=max_events_per_file, max_total_events=max_total_events,
            )
            cache.put(subject.sha, facts)
            records.append(record_from_facts(subject, facts))
            status.update(subject, "done", source="fresh")
            if on_subject is not None:
                on_subject(subject, "fresh", None)
        except RepoScanError as exc:
            errors.append({"target": subject.target, "sha": subject.sha, "error": str(exc)})
            status.update(subject, "error", source="fresh", error=str(exc))
            if on_subject is not None:
                on_subject(subject, "error", str(exc))
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)

    dataset = aggregate(records)
    dataset["errors"] = sorted(errors, key=lambda e: (e["target"], e["sha"]))
    return dataset
