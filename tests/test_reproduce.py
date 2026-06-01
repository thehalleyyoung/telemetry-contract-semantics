"""Tests for the one-command reproduction and its determinism manifest.

``reproduce`` must regenerate every offline artifact deterministically: running
it twice yields identical bytes, and ``check_reproduction`` agrees with the
committed manifest. Artifacts that legitimately embed measured runtime are
excluded from the manifest by design (asserted here so the exclusion is not
silently widened).
"""

from __future__ import annotations

import json
from pathlib import Path

from telemetry_contracts.reproduce import (
    GENERATORS,
    check_reproduction,
    run_reproduction,
)

_ROOT = Path(__file__).resolve().parents[1]


def test_reproduction_is_byte_deterministic(tmp_path):
    first = run_reproduction(_ROOT, write=False)["artifacts"]
    second = run_reproduction(_ROOT, write=False)["artifacts"]
    assert first == second, "reproduction is not byte-deterministic"
    assert len(first) >= 12


def test_check_matches_committed_manifest():
    report = check_reproduction(_ROOT)
    assert report["ok"], (
        f"reproduction drift: mismatched={report.get('mismatched')} "
        f"missing={report.get('missing')} extra={report.get('extra')}"
    )


def test_timing_bearing_reports_are_excluded_from_manifest():
    artifacts = set(run_reproduction(_ROOT, write=False)["artifacts"])
    # These embed measured runtime or non-portable absolute paths / commit hash;
    # they must not be in a cross-host/cross-commit determinism manifest.
    assert "reports/current_impact.json" not in artifacts
    assert "reports/current_impact.md" not in artifacts
    assert "reports/current_impact.sarif" not in artifacts
    assert "reports/current_impact_taxonomy.json" not in artifacts
    assert "docs/claims_evidence_matrix.json" not in artifacts
    # But the portable, frozen-input-derived artifacts must be present.
    assert "reports/paper_tables.md" in artifacts
    assert "reports/gold_evaluation.json" in artifacts


def test_manifest_covers_evaluation_and_demo_artifacts():
    artifacts = set(run_reproduction(_ROOT, write=False)["artifacts"])
    assert "reports/gold_evaluation.json" in artifacts
    assert "reports/baseline_comparison.json" in artifacts
    assert "playground/assets/telemetry_contracts.zip" in artifacts
    assert "docs/launch/social_card.svg" in artifacts


def test_committed_manifest_is_valid_json():
    manifest = json.loads((_ROOT / "reports" / "reproduce_manifest.json").read_text())
    assert manifest["schema"] == "telemetry-contracts/reproduce-manifest@1"
    assert manifest["artifacts"]
    assert all(len(h) == 64 for h in manifest["artifacts"].values())


def test_generators_registered():
    assert len(GENERATORS) >= 5
