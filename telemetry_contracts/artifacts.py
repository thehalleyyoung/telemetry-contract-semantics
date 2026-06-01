"""Deterministic, content-addressable persistence for pipeline artifacts.

Every stage of the staged loop can be written to disk as a JSON artifact keyed
to the acquisition commit SHA and carrying a provenance block (source commit,
stage, generator, pipeline options, and a content hash of the canonical bytes).
This makes a run fully reconstructable and auditable from inputs, and lets later
stages (or a later run on the same SHA) diff against an exact earlier snapshot.

Pure stdlib. No wall-clock timestamps are recorded — artifacts are byte-stable
for identical inputs so they can be compared in CI and across machines.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

GENERATOR = "telemetry-contracts/pipeline@1"


def canonical_bytes(obj: Any) -> bytes:
    """Canonical JSON encoding used for content hashing (stable across machines)."""

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def content_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def clone_cache_key(repo: str, ref: str | None) -> str:
    """Stable cache key for a (repo, ref) pair so re-runs can skip re-cloning."""

    return hashlib.sha256(f"{repo}@{ref or 'HEAD'}".encode("utf-8")).hexdigest()[:16]


def _normalize_for_persist(report: dict[str, Any]) -> dict[str, Any]:
    """Strip machine-specific values (absolute paths) so artifacts are portable.

    The characterization manifest records the clone/working-copy root, which is
    an absolute, environment-specific path. The persisted artifacts drop it
    entirely (it is not part of the content being characterized) so content
    hashes match across machines AND across clone strategies for the same
    commit -- e.g. an anonymous temp clone (basename "repo") and a
    content-addressed cache clone (basename = cache key) of the *same* commit
    must hash identically. Provenance still anchors everything to the commit SHA.
    """

    clone = json.loads(json.dumps(report))  # deep copy via stdlib
    char = clone.get("characterization")
    if isinstance(char, dict):
        manifest = char.get("manifest")
        if isinstance(manifest, dict) and "root" in manifest:
            manifest["root"] = None
            manifest["root_normalized"] = True
    return clone


def _provenance(stage: str, *, source_commit: str | None, options: dict[str, Any], payload: Any) -> dict[str, Any]:
    return {
        "schema": "telemetry-contracts/provenance@1",
        "stage": stage,
        "generator": GENERATOR,
        "source_commit": source_commit,
        "pipeline_options": options,
        "content_sha256": content_sha256(payload),
    }


def _write_json(path: Path, payload: Any) -> str:
    """Write canonical JSON; return the content hash of what was written."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
    return content_sha256(payload)


def write_pipeline_artifacts(
    report: dict[str, Any],
    out_dir: str | Path,
    *,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist a ``run_pipeline`` report as a SHA-keyed artifact tree.

    Returns an index dict (also written as ``index.json``) listing each artifact
    with its relative path, stage, and content hash. The returned index contains
    NO absolute paths, so it is safe to embed in a deterministic report.
    """

    options = dict(options or {})
    report = _normalize_for_persist(report)
    char = report.get("characterization") or {}
    commit = (char.get("manifest") or {}).get("commit")
    sha_key = commit or "unknown-sha"
    root = Path(out_dir) / sha_key

    written: list[dict[str, Any]] = []

    def emit(rel: str, stage: str, payload: Any) -> None:
        prov = _provenance(stage, source_commit=commit, options=options, payload=payload)
        wrapped = {"provenance": prov, "artifact": payload}
        digest = _write_json(root / rel, wrapped)
        written.append({"path": rel, "stage": stage, "content_sha256": digest})

    emit("characterization.json", "characterize", char)
    if report.get("baseline") is not None:
        emit("baseline.json", "baseline", report["baseline"])

    for round_report in report.get("rounds", []):
        n = round_report["round"]
        base = f"rounds/round-{n:03d}"
        emit(f"{base}/plan.json", "plan", round_report.get("plan"))
        if "code_proposals" in round_report:
            emit(f"{base}/code-proposals.json", "code-proposals", round_report["code_proposals"])
        if "application_manifest" in round_report:
            emit(f"{base}/application-manifest.json", "apply", round_report["application_manifest"])
        emit(f"{base}/differential.json", "differential", round_report.get("differential"))

    if report.get("impact_ledger") is not None:
        emit("impact_ledger.json", "ledger", report["impact_ledger"])
    final = report.get("final") or {}
    if final.get("overall_differential") is not None:
        # Keyed to both states: the source commit and the synthetic after-state.
        overall = dict(final["overall_differential"])
        overall["before_state"] = sha_key
        overall["after_state"] = f"{sha_key}+synthetic"
        emit("differential-overall.json", "differential", overall)

    emit("pipeline.json", "pipeline", report)

    index = {
        "schema": "telemetry-contracts/artifact-index@1",
        "source_commit": commit,
        "sha_key": sha_key,
        "generator": GENERATOR,
        "pipeline_options": options,
        "artifacts": sorted(written, key=lambda a: a["path"]),
    }
    _write_json(root / "index.json", index)
    return index
