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
