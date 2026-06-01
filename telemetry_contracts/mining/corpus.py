"""Declarative, pinned-commit subject corpus for the mining study.

A corpus manifest is a small JSON document that pins every subject repository to
an exact commit SHA, so the study is replayable byte-for-byte and never depends
on live search at analysis time. The manifest also records the *selection
protocol* (why these repos) and each subject's license, so the sample is
defensible and redistributing the derived results is clearly permissible.

The format is intentionally tiny and stdlib-only::

    {
      "schema": "telemetry-contracts/corpus@1",
      "selection_protocol": {
        "description": "...",
        "criteria": ["language=...", "min_stars=...", "has-telemetry heuristic", ...],
        "exclusions": ["forks", "archived", ...]
      },
      "subjects": [
        {"target": "owner/repo", "sha": "<40-hex>", "host": "github",
         "license": "MIT", "rationale": "ships JSONL logs", "tier": 1}
      ]
    }

``target`` accepts the same shorthand as ``scan-repo`` (``owner/repo``,
``<host>/owner/repo``, ``gh:``/``gl:``/``bb:`` prefixes, or a full URL).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..repo_scan import RepoScanError, parse_repo_target

SCHEMA = "telemetry-contracts/corpus@1"

# A git SHA: a full 40-hex object name (we require full SHAs so a manifest can
# never be ambiguous about which commit was studied).
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class CorpusManifestError(ValueError):
    """Raised when a corpus manifest is malformed."""


@dataclass(frozen=True)
class CorpusSubject:
    """One pinned subject repository in the corpus."""

    target: str
    sha: str
    host: str
    license: str
    rationale: str
    tier: int

    @property
    def clone_url(self) -> str:
        """The deterministic clone URL this subject resolves to."""

        return parse_repo_target(self.target)

    @property
    def identity(self) -> str:
        """A stable, human-readable identity (``target@<sha12>``)."""

        return f"{self.target}@{self.sha[:12]}"

    def to_row(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "sha": self.sha,
            "host": self.host,
            "license": self.license,
            "rationale": self.rationale,
            "tier": self.tier,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CorpusManifestError(message)


def _infer_host(target: str) -> str:
    """Best-effort host label derived from the (already validated) target."""

    url = parse_repo_target(target)
    for host in ("github", "gitlab", "bitbucket", "codeberg"):
        if host + "." in url:
            return host
    return "other"


def parse_corpus_manifest(data: Any) -> tuple[dict[str, Any], list[CorpusSubject]]:
    """Validate a parsed manifest object and return (selection_protocol, subjects).

    Raises :class:`CorpusManifestError` on any structural problem. Validation is
    strict and deterministic so a bad corpus fails loudly rather than silently
    skewing the study.
    """

    _require(isinstance(data, dict), "manifest must be a JSON object")
    _require(data.get("schema") == SCHEMA, f"manifest schema must be {SCHEMA!r}")

    protocol = data.get("selection_protocol", {})
    _require(isinstance(protocol, dict), "selection_protocol must be an object")

    raw_subjects = data.get("subjects")
    _require(isinstance(raw_subjects, list) and raw_subjects, "subjects must be a non-empty array")

    subjects: list[CorpusSubject] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_subjects):
        _require(isinstance(raw, dict), f"subjects[{i}] must be an object")
        target = raw.get("target")
        _require(isinstance(target, str) and target.strip(), f"subjects[{i}].target must be a non-empty string")
        target = target.strip()
        # Reject targets the cloner could not resolve, up front.
        try:
            parse_repo_target(target)
        except RepoScanError as exc:
            raise CorpusManifestError(f"subjects[{i}].target invalid: {exc}") from exc

        sha = raw.get("sha")
        _require(isinstance(sha, str) and _SHA_RE.match(sha.lower() if isinstance(sha, str) else ""),
                 f"subjects[{i}].sha must be a full 40-character hex commit SHA")
        sha = sha.lower()

        host = raw.get("host")
        if host is None:
            host = _infer_host(target)
        _require(isinstance(host, str) and host, f"subjects[{i}].host must be a string")

        license_ = raw.get("license", "UNKNOWN")
        _require(isinstance(license_, str) and license_, f"subjects[{i}].license must be a string")

        rationale = raw.get("rationale", "")
        _require(isinstance(rationale, str), f"subjects[{i}].rationale must be a string")

        tier = raw.get("tier", 1)
        _require(isinstance(tier, int) and not isinstance(tier, bool) and tier >= 1,
                 f"subjects[{i}].tier must be a positive integer")

        key = f"{target}@{sha}"
        _require(key not in seen, f"duplicate subject {key}")
        seen.add(key)

        subjects.append(
            CorpusSubject(
                target=target, sha=sha, host=host,
                license=license_, rationale=rationale, tier=tier,
            )
        )

    # Deterministic order: by (tier, target, sha) regardless of file ordering.
    subjects.sort(key=lambda s: (s.tier, s.target, s.sha))
    return protocol, subjects


def load_corpus_manifest(path: str | Path) -> tuple[dict[str, Any], list[CorpusSubject]]:
    """Load and validate a corpus manifest from ``path``."""

    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CorpusManifestError(f"corpus manifest not found: {p}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusManifestError(f"could not read corpus manifest {p}: {exc}") from exc
    return parse_corpus_manifest(data)
