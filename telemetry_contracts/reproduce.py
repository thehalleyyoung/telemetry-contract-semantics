"""One-command, byte-deterministic reproduction of every offline artifact.

``reproduce`` regenerates the figures, tables, and headline numbers that the
evaluation and paper depend on, *entirely offline* from the frozen inputs (the
built-in benchmark, the curated gold set, the recorded-baseline cache, and the
package source), and records a SHA-256 manifest of every produced artifact.

Two modes back the determinism/artifact-evaluation story:

* ``run_reproduction(write=True)`` regenerates all artifacts in place and writes
  ``reports/reproduce_manifest.json`` (sorted ``artifact -> sha256``).
* ``check_reproduction()`` regenerates into a temporary tree and verifies every
  artifact's bytes match the committed manifest — so CI can fail on any
  nondeterminism without trusting the working tree.

Everything here is pure stdlib and uses no network and no wall-clock, so the
manifest is stable across runs, hosts, and Python versions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .claims import write_claims_evidence_matrix
from .evaluation import compare_baselines, load_gold_set, score_gold_set
from .regenerate import regenerate_artifacts

_MANIFEST_REL = "reports/reproduce_manifest.json"
_GOLD = "benchmarks/ground_truth/curated.jsonl"
_BASELINE_CACHE = "benchmarks/baselines/llm_recorded.json"

# Artifacts that are regenerated but deliberately excluded from the
# cross-host/cross-commit determinism manifest, because their bytes legitimately
# depend on the environment rather than on the frozen inputs:
#   * current_impact.{json,md} embed *measured runtime* (a performance signal);
#   * current_impact.sarif and the taxonomy embed *absolute filesystem paths* of
#     the benchmark's case studies (machine-specific, not portable);
#   * the claims matrix embeds the *git commit hash* (changes every commit).
# Everything else in the manifest is a pure function of the frozen inputs and is
# byte-identical across runs, hosts, and Python versions.
_NON_PORTABLE: frozenset[str] = frozenset(
    {
        "reports/current_impact.json",
        "reports/current_impact.md",
        "reports/current_impact.sarif",
        "reports/current_impact_taxonomy.json",
        "reports/current_impact_taxonomy.md",
        "docs/claims_evidence_matrix.json",
    }
)


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def _gen_core(root: Path) -> list[str]:
    """Benchmark reports, taxonomy, paper tables, claims matrix.

    All are regenerated in place; only the portable, frozen-input-derived ones
    (the paper tables) enter the determinism manifest — see ``_NON_PORTABLE``.
    """
    result = regenerate_artifacts(root, write=True)
    artifacts = list(result["artifacts"])
    artifacts.append("docs/claims_evidence_matrix.json")
    return artifacts


def _gen_gold(root: Path) -> list[str]:
    items = load_gold_set(str(root / _GOLD))
    dataset = score_gold_set(items)
    rel = "reports/gold_evaluation.json"
    _write(root, rel, json.dumps(dataset, indent=2, sort_keys=True))
    return [rel]


def _gen_baselines(root: Path) -> list[str]:
    items = load_gold_set(str(root / _GOLD))
    cache = json.loads((root / _BASELINE_CACHE).read_text(encoding="utf-8"))
    comparison = compare_baselines(items, cache)
    rel = "reports/baseline_comparison.json"
    _write(root, rel, json.dumps(comparison, indent=2, sort_keys=True))
    return [rel]


def _gen_playground(root: Path) -> list[str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_repro_playground_build", root / "playground" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build_bundle()
    rels = ["playground/assets/telemetry_contracts.zip", "playground/assets/examples.json"]
    for path in sorted((root / "playground" / "assets" / "examples").glob("*.jsonl")):
        rels.append(path.relative_to(root).as_posix())
    return rels


def _gen_launch(root: Path) -> list[str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_repro_launch_build", root / "docs" / "launch" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build()
    return [
        "docs/launch/demo.svg",
        "docs/launch/demo.cast",
        "docs/launch/social_card.svg",
        "docs/launch/demo_transcript.txt",
    ]


# Ordered so dependencies (e.g. taxonomy needs the benchmark JSON) run first.
GENERATORS: list[Callable[[Path], list[str]]] = [
    _gen_core,
    _gen_gold,
    _gen_baselines,
    _gen_playground,
    _gen_launch,
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _regenerate(root: Path) -> list[str]:
    produced: list[str] = []
    for generator in GENERATORS:
        produced.extend(generator(root))
    # Drop non-portable artifacts from the manifest set; keep a stable order.
    return sorted(set(produced) - _NON_PORTABLE)


def run_reproduction(repo_root: str | Path = ".", *, write: bool = True) -> dict[str, Any]:
    """Regenerate all offline artifacts in place and return the SHA-256 manifest."""
    root = Path(repo_root)
    artifacts = _regenerate(root)
    manifest = {rel: _sha256(root / rel) for rel in artifacts}
    report = {
        "schema": "telemetry-contracts/reproduce-manifest@1",
        "artifacts": manifest,
        "summary": {"artifacts": len(manifest)},
    }
    if write:
        _write(root, _MANIFEST_REL, json.dumps(report, indent=2, sort_keys=True))
    return report


def check_reproduction(repo_root: str | Path = ".") -> dict[str, Any]:
    """Regenerate and verify every artifact matches the committed manifest.

    Returns a report with ``ok`` plus any ``mismatched``/``missing`` artifacts.
    Does not require a clean working tree: it compares freshly computed hashes to
    the committed ``reports/reproduce_manifest.json``.
    """
    root = Path(repo_root)
    committed_path = root / _MANIFEST_REL
    if not committed_path.exists():
        return {"ok": False, "error": f"missing committed manifest: {_MANIFEST_REL}"}
    committed = json.loads(committed_path.read_text(encoding="utf-8")).get("artifacts", {})

    artifacts = _regenerate(root)
    fresh = {rel: _sha256(root / rel) for rel in artifacts}

    mismatched = sorted(rel for rel in fresh if rel in committed and fresh[rel] != committed[rel])
    missing = sorted(set(committed) - set(fresh))
    extra = sorted(set(fresh) - set(committed))
    ok = not mismatched and not missing and not extra
    return {
        "schema": "telemetry-contracts/reproduce-check@1",
        "ok": ok,
        "mismatched": mismatched,
        "missing": missing,
        "extra": extra,
        "summary": {"artifacts": len(fresh), "mismatched": len(mismatched), "missing": len(missing), "extra": len(extra)},
    }
