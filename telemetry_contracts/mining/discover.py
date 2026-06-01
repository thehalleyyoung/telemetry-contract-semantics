"""Discovery helper: *propose* corpus candidates from public search (pure stdlib).

This is a curation aid, **not** part of the study and **never executed by tests**.
It queries public repository search (GitHub, optionally GitLab) by language and
popularity and emits a *seed list* of candidate repositories. Search results are
live and non-deterministic, so the output is deliberately a proposal file that a
human (or the deterministic ``corpus-verify`` path) must review and pin to an
exact commit SHA before a candidate ever enters a corpus manifest.

Keeping discovery strictly separate from the manifest preserves the study's
byte-reproducibility: the manifest only ever contains pinned, verified subjects.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_GITHUB_SEARCH = "https://api.github.com/search/repositories"
_GITLAB_SEARCH = "https://gitlab.com/api/v4/projects"

SEED_SCHEMA = "telemetry-contracts/corpus-seed@1"


def _http_get_json(url: str, *, token: str | None, timeout: int = 30) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "telemetry-contracts-corpus-discovery",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed hosts)
        return json.loads(response.read().decode("utf-8"))


def search_github(
    *,
    language: str,
    min_stars: int = 50,
    limit: int = 20,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Propose GitHub repositories matching ``language`` with >= ``min_stars`` stars."""

    query = f"language:{language} stars:>={min_stars} archived:false fork:false"
    params = urllib.parse.urlencode({
        "q": query, "sort": "stars", "order": "desc",
        "per_page": str(max(1, min(limit, 100))),
    })
    payload = _http_get_json(f"{_GITHUB_SEARCH}?{params}", token=token)
    candidates: list[dict[str, Any]] = []
    for item in payload.get("items", [])[:limit]:
        candidates.append({
            "target": item["full_name"],
            "host": "github",
            "default_branch": item.get("default_branch"),
            "stars": int(item.get("stargazers_count", 0)),
            "license": (item.get("license") or {}).get("spdx_id") or "UNKNOWN",
            "note": f"language:{language} stars>={min_stars} (verify telemetry + pin SHA before use)",
        })
    return candidates


def search_gitlab(
    *,
    language: str | None = None,
    min_stars: int = 20,
    limit: int = 20,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Propose popular public GitLab projects (best-effort; star-ordered)."""

    params = urllib.parse.urlencode({
        "order_by": "star_count", "sort": "desc",
        "per_page": str(max(1, min(limit, 100))), "visibility": "public",
        "min_access_level": "10",
    })
    try:
        payload = _http_get_json(f"{_GITLAB_SEARCH}?{params}", token=token)
    except (urllib.error.URLError, ValueError):
        return []
    candidates: list[dict[str, Any]] = []
    for item in payload[:limit] if isinstance(payload, list) else []:
        if int(item.get("star_count", 0)) < min_stars:
            continue
        candidates.append({
            "target": f"gl:{item['path_with_namespace']}",
            "host": "gitlab",
            "default_branch": item.get("default_branch"),
            "stars": int(item.get("star_count", 0)),
            "license": "UNKNOWN",
            "note": "gitlab popular project (verify telemetry + pin SHA before use)",
        })
    return candidates


_GITHUB_CODE_SEARCH = "https://api.github.com/search/code"


def search_github_code(
    *,
    query: str,
    limit: int = 50,
    token: str | None = None,
) -> list[dict[str, Any]]:
    """Propose repositories that *commit* telemetry-shaped files matching ``query``.

    GitHub code search surfaces the file hits; we reduce them to unique,
    non-fork repositories. This is how telemetry-bearing repositories (which the
    repository-metadata search cannot find) enter the candidate stream. The
    output is still a proposal — every hit must be cloned, verified, and pinned
    before it can join a manifest.
    """

    params = urllib.parse.urlencode({"q": query, "per_page": str(max(1, min(limit, 100)))})
    try:
        payload = _http_get_json(f"{_GITHUB_CODE_SEARCH}?{params}", token=token)
    except (urllib.error.URLError, ValueError):
        return []
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        repo = item.get("repository", {})
        full_name = repo.get("full_name")
        if not full_name or repo.get("fork") or full_name in seen:
            continue
        seen.add(full_name)
        candidates.append({
            "target": full_name,
            "host": "github",
            "default_branch": repo.get("default_branch"),
            "license": "UNKNOWN",
            "example_path": item.get("path"),
            "note": f"committed telemetry file matched code search (verify + pin SHA): {query}",
        })
    return candidates


def discover_candidates(
    *,
    languages: list[str],
    min_stars: int = 50,
    per_language: int = 20,
    include_gitlab: bool = False,
    token: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic-shaped *seed proposal* (contents are live search)."""

    candidates: list[dict[str, Any]] = []
    for language in languages:
        candidates.extend(
            search_github(language=language, min_stars=min_stars, limit=per_language, token=token)
        )
    if include_gitlab:
        candidates.extend(search_gitlab(min_stars=max(10, min_stars // 2), limit=per_language, token=token))

    # De-duplicate by target, keep a stable sorted order for review.
    unique: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        unique.setdefault(candidate["target"], candidate)
    ordered = [unique[target] for target in sorted(unique)]

    return {
        "schema": SEED_SCHEMA,
        "query": {
            "languages": sorted(languages),
            "min_stars": min_stars,
            "per_language": per_language,
            "include_gitlab": include_gitlab,
        },
        "note": (
            "PROPOSAL ONLY. Each candidate must be verified to ship parseable "
            "telemetry and pinned to an exact commit SHA before being added to a "
            "corpus manifest. This file is never consumed by the study."
        ),
        "candidates": ordered,
    }
