"""Offline tests for the discovery helper (live HTTP is monkeypatched out)."""

from __future__ import annotations

from telemetry_contracts.mining import discover


def test_discover_candidates_shape_and_proposal_warning(monkeypatch):
    def fake_get(url, *, token, timeout=30):
        return {
            "items": [
                {"full_name": "o/repo-b", "default_branch": "main",
                 "stargazers_count": 200, "license": {"spdx_id": "MIT"}},
                {"full_name": "o/repo-a", "default_branch": "main",
                 "stargazers_count": 150, "license": None},
            ]
        }

    monkeypatch.setattr(discover, "_http_get_json", fake_get)
    seed = discover.discover_candidates(languages=["Python"], min_stars=50, per_language=10)

    assert seed["schema"] == discover.SEED_SCHEMA
    assert "PROPOSAL ONLY" in seed["note"]
    # Candidates are de-duplicated and sorted by target for review.
    targets = [c["target"] for c in seed["candidates"]]
    assert targets == sorted(targets)
    assert {"o/repo-a", "o/repo-b"} == set(targets)
    for candidate in seed["candidates"]:
        assert candidate["host"] == "github"
        assert "verify telemetry + pin SHA" in candidate["note"]


def test_discover_deduplicates_across_languages(monkeypatch):
    monkeypatch.setattr(
        discover, "_http_get_json",
        lambda url, *, token, timeout=30: {
            "items": [{"full_name": "o/dup", "default_branch": "main",
                       "stargazers_count": 99, "license": None}]
        },
    )
    seed = discover.discover_candidates(languages=["Python", "Go"], min_stars=10)
    assert [c["target"] for c in seed["candidates"]] == ["o/dup"]
    assert seed["query"]["languages"] == ["Go", "Python"]


def test_search_github_code_reduces_to_unique_non_fork_repos(monkeypatch):
    def fake_get(url, *, token, timeout=30):
        return {
            "items": [
                {"path": "logs/a.jsonl", "repository": {
                    "full_name": "o/keep", "fork": False, "default_branch": "main"}},
                {"path": "logs/b.jsonl", "repository": {
                    "full_name": "o/keep", "fork": False, "default_branch": "main"}},  # dup repo
                {"path": "x.jsonl", "repository": {
                    "full_name": "o/forked", "fork": True, "default_branch": "main"}},
            ]
        }

    monkeypatch.setattr(discover, "_http_get_json", fake_get)
    cands = discover.search_github_code(query='"trace_id" extension:jsonl')
    targets = [c["target"] for c in cands]
    assert targets == ["o/keep"]  # dup collapsed, fork excluded
    assert cands[0]["host"] == "github"
    assert cands[0]["example_path"] == "logs/a.jsonl"


def test_search_github_code_tolerates_network_failure(monkeypatch):
    import urllib.error

    def boom(url, *, token, timeout=30):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(discover, "_http_get_json", boom)
    assert discover.search_github_code(query="anything") == []
