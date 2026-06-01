"""Curate verified corpus subjects from candidate repositories (network + git).

This bridges *discovery* (a non-deterministic proposal of candidate repositories)
and the *manifest* (a frozen list of pinned, verified subjects). For each
candidate it shallow-clones the current default branch, reads the exact commit
SHA at ``HEAD`` (an honest pin to a real commit — never a fabricated SHA), scans
the checkout, and keeps the subject only if it genuinely clones, verifies, and —
when ``require_telemetry`` is set — actually ships parseable telemetry.

Like the discovery and download helpers this touches the network and git, so it
is **never executed by the test suite**; the offline tests exercise its pure
pieces (host inference, subject reduction, manifest assembly) with the clone step
injected.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

from ..repo_scan import RepoScanError, clone_repo
from .corpus import CorpusSubject
from .runner import _safe_target
from .study import analyze_checkout

CURATE_SCHEMA = "telemetry-contracts/corpus@1"

_HOST_PREFIXES = {"gh:": "github", "gl:": "gitlab", "bb:": "bitbucket"}
_HOST_DOMAINS = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
    "codeberg.org": "codeberg",
}


def infer_host(target: str) -> str:
    """Infer the canonical host token from a candidate target string."""

    t = target.strip()
    for prefix, host in _HOST_PREFIXES.items():
        if t.startswith(prefix):
            return host
    lowered = t.lower()
    for domain, host in _HOST_DOMAINS.items():
        if domain in lowered:
            return host
    # Bare ``owner/repo`` shorthand defaults to GitHub (same rule as parse_repo_target).
    return "github"


def _git_head_sha(checkout: Path, *, timeout: int = 60) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RepoScanError(
            f"could not read HEAD of {checkout}: {(result.stderr or '').strip()}"
        )
    sha = result.stdout.strip()
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise RepoScanError(f"unexpected HEAD object id {sha!r} for {checkout}")
    return sha


def candidate_subject(
    target: str,
    *,
    work_dir: Path,
    license: str = "UNKNOWN",
    rationale: str | None = None,
    tier: int = 2,
    require_telemetry: bool = True,
    service: str | None = None,
    max_files: int = 300,
    max_events_per_file: int = 50_000,
    max_total_events: int = 200_000,
    clone: Callable[..., Any] = clone_repo,
    analyze: Callable[..., dict[str, Any]] = analyze_checkout,
) -> dict[str, Any] | None:
    """Clone, pin, and verify a single candidate.

    Returns a manifest subject dict augmented with the verified facts, or ``None``
    when the candidate fails to clone/verify or (with ``require_telemetry``) ships
    no parseable telemetry. ``clone``/``analyze`` are injectable for offline tests.
    """

    host = infer_host(target)
    checkout = Path(work_dir) / host / _safe_target(target)
    checkout.parent.mkdir(parents=True, exist_ok=True)
    if checkout.exists():
        # Idempotent: a previous curation run already placed this checkout.
        pass
    else:
        try:
            clone(target, checkout, depth=1)
        except RepoScanError:
            return None
    try:
        sha = _git_head_sha(checkout)
        facts = analyze(
            checkout, service=service, max_files=max_files,
            max_events_per_file=max_events_per_file, max_total_events=max_total_events,
        )
    except (RepoScanError, subprocess.SubprocessError):
        return None

    if require_telemetry and not facts.get("has_telemetry"):
        return None

    auto_rationale = rationale or (
        f"ships parseable telemetry ({facts.get('event_count', 0)} events, "
        f"formats: {', '.join(facts.get('formats', []) or ['none'])})"
        if facts.get("has_telemetry")
        else "independent repository (no-telemetry graceful path)"
    )
    return {
        "target": target,
        "sha": sha,
        "host": host,
        "license": license or "UNKNOWN",
        "rationale": auto_rationale,
        "tier": int(tier),
        "_facts": {
            "has_telemetry": bool(facts.get("has_telemetry")),
            "event_count": int(facts.get("event_count", 0)),
            "formats": list(facts.get("formats", []) or []),
        },
    }


def build_manifest(
    subjects: list[dict[str, Any]],
    *,
    description: str,
    tier_note: str | None = None,
) -> dict[str, Any]:
    """Assemble a frozen, deterministically-ordered corpus manifest."""

    clean: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for subject in subjects:
        key = (subject["host"], subject["target"])
        if key in seen:
            continue
        seen.add(key)
        clean.append({
            "target": subject["target"],
            "sha": subject["sha"],
            "host": subject["host"],
            "license": subject.get("license", "UNKNOWN"),
            "rationale": subject.get("rationale", ""),
            "tier": int(subject.get("tier", 2)),
        })
    clean.sort(key=lambda s: (s["host"], s["target"], s["sha"]))
    manifest: dict[str, Any] = {
        "schema": CURATE_SCHEMA,
        "selection_protocol": {
            "description": description,
            "criteria": [
                "public repository reachable without authentication",
                "ships at least one parseable telemetry/log file in a recognised format",
                "authored independently of this project (no contract or convention adoption)",
            ],
            "exclusions": ["forks", "archived repositories", "auth-required repositories"],
        },
        "subjects": clean,
    }
    if tier_note:
        manifest["selection_protocol"]["notes"] = tier_note
    return manifest


def curate_corpus(
    candidates: Iterable[str | dict[str, Any]],
    *,
    work_dir: str | Path,
    require_telemetry: bool = True,
    tier: int = 2,
    limit: int | None = None,
    service: str | None = None,
    on_candidate: Callable[[str, dict[str, Any] | None], None] | None = None,
    clone: Callable[..., Any] = clone_repo,
    analyze: Callable[..., dict[str, Any]] = analyze_checkout,
) -> list[dict[str, Any]]:
    """Verify a stream of candidates and return the kept subjects (with facts).

    Stops once ``limit`` subjects have been kept. ``candidates`` items may be a
    bare target string or a dict with ``target``/``license``/``rationale`` keys.
    """

    kept: list[dict[str, Any]] = []
    work = Path(work_dir)
    for candidate in candidates:
        if limit is not None and len(kept) >= limit:
            break
        if isinstance(candidate, str):
            target, license_, rationale = candidate, "UNKNOWN", None
        else:
            target = candidate["target"]
            license_ = candidate.get("license", "UNKNOWN")
            rationale = candidate.get("rationale")
        subject = candidate_subject(
            target, work_dir=work, license=license_, rationale=rationale,
            tier=tier, require_telemetry=require_telemetry, service=service,
            clone=clone, analyze=analyze,
        )
        if on_candidate is not None:
            on_candidate(target, subject)
        if subject is not None:
            kept.append(subject)
    return kept
