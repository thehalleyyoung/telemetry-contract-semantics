"""The high-impact filter: a written, mechanical rubric for scoring additions.

The project's guiding principle is that every *addition* — whether a proposed
instrumentation change for a target repo, or a capability shipped in this tool —
must earn its complexity by the analytic signal it unlocks. This module turns
that principle into a deterministic, reproducible score:

    impact = analytic signal gained  /  added surface area

* **Analytic signal gained** is derived *mechanically* from existing artifacts —
  the number of incident questions a change unblocks plus the number of runtime
  signal names / correlation edges it introduces. It is never a free-form or
  model-supplied judgement, so the score is reproducible.
* **Added surface area** is the cost: source lines added plus distinct files
  touched.

The score is a *rubric signal*, not an automatic gate: a tiny change can score
highly by touching little, and necessary scaffolding can score low, so the
breakdown is always reported next to the score for human judgement. All
arithmetic is fixed-point (integer milli-units) to keep results byte-identical
across machines.
"""

from __future__ import annotations

from typing import Any

RUBRIC = "telemetry-contracts/high-impact-filter@1"

# Score thresholds (milli-units of signal per unit of surface area).
_STRONG = 250
_MODERATE = 100


def _verdict(impact_milli: int, surface_area: int) -> str:
    if surface_area <= 0:
        return "indeterminate-zero-surface"
    if impact_milli >= _STRONG:
        return "high-impact"
    if impact_milli >= _MODERATE:
        return "moderate-impact"
    return "low-impact"


def score_addition(
    *,
    questions_unblocked: int,
    signals_introduced: int,
    edges_introduced: int = 0,
    lines_added: int,
    files_touched: int,
) -> dict[str, Any]:
    """Score one addition by analytic-signal-per-surface-area (fixed-point).

    All inputs are non-negative integers derived mechanically from existing
    artifacts. ``impact_milli`` is ``1000 * signal // surface`` (integer), so the
    score is deterministic. Zero surface area yields an explicit indeterminate
    verdict rather than a division error.
    """

    signal = max(0, questions_unblocked) + max(0, signals_introduced) + max(0, edges_introduced)
    surface = max(0, lines_added) + max(0, files_touched)
    impact_milli = (signal * 1000) // surface if surface > 0 else 0
    return {
        "rubric": RUBRIC,
        "analytic_signal": signal,
        "surface_area": surface,
        "impact_milli": impact_milli,
        "verdict": _verdict(impact_milli, surface),
        "breakdown": {
            "questions_unblocked": max(0, questions_unblocked),
            "signals_introduced": max(0, signals_introduced),
            "edges_introduced": max(0, edges_introduced),
            "lines_added": max(0, lines_added),
            "files_touched": max(0, files_touched),
        },
        "note": (
            "rubric signal, not an automatic gate; review the breakdown — a tiny "
            "change can score high and necessary scaffolding can score low"
        ),
    }


def _snippet_lines(snippet: str) -> int:
    # Non-empty added lines, deterministic.
    return sum(1 for line in snippet.splitlines() if line.strip())


def score_code_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    """Apply the rubric to a generated code proposal (mechanical inputs only)."""

    validation = proposal.get("validation", {})
    names = validation.get("present_in_source") or validation.get("intended_names") or []
    questions = proposal.get("questions_unblocked", [])
    patch = proposal.get("patch") or {}
    files_touched = 1 if patch.get("path") else 1
    lines_added = patch.get("added_lines")
    if not isinstance(lines_added, int):
        lines_added = _snippet_lines(proposal.get("snippet", ""))
    # Correlation instrumentation introduces ordering edges between the correlated
    # signals; count one edge per introduced correlation name as a conservative,
    # mechanical proxy.
    edges = len(names) if proposal.get("gap") == "missing-correlation" else 0
    return score_addition(
        questions_unblocked=len(questions),
        signals_introduced=len(names),
        edges_introduced=edges,
        lines_added=lines_added,
        files_touched=files_touched,
    )


def _recommendation(predicted: int, realized: int, surface: int, confounded: bool) -> str:
    if confounded:
        return "keep-confounded-attribution"
    if surface <= 0:
        return "review-zero-surface"
    if realized <= 0:
        return "prune-no-realized-impact"
    if predicted > 0 and realized * 2 < predicted:
        return "merge-underperformed-vs-prediction"
    return "keep"


def feature_scorecard(rounds: list[dict[str, Any]], ledger: list[dict[str, Any]]) -> dict[str, Any]:
    """Re-score every applied change after the fact against the rubric.

    This is tool/maintenance metadata about the *applied changes from this real
    run* (predicted vs realized analytic impact per unit of surface area) — it is
    deliberately NOT a finding about the analyzed repository and emits no
    taxonomy codes. When a single round applied multiple changes their realized
    deltas cannot be isolated, so attribution is marked ``confounded`` honestly.
    """

    by_round = {r["round"]: r for r in rounds}
    entries: list[dict[str, Any]] = []
    for record in ledger:
        rnd = by_round.get(record["round"])
        if rnd is None or record.get("quarantined"):
            continue
        proposals = rnd.get("code_proposals", {}).get("proposals", [])
        applied_changes = rnd.get("plan", {}).get("planned_changes", [])
        confounded = len(applied_changes) > 1
        round_surface = 0
        for p in proposals:
            score = p.get("impact_score") or score_code_proposal(p)
            round_surface += score["surface_area"]
        predicted = record.get("predicted_score_points", 0)
        realized = record.get("realized_score_delta", 0)
        impact_milli = (max(0, realized) * 1000) // round_surface if round_surface > 0 else 0
        entries.append({
            "round": record["round"],
            "changes_applied": record.get("changes_applied", 0),
            "predicted_score_points": predicted,
            "realized_score_delta": realized,
            "surface_area": round_surface,
            "realized_impact_milli": impact_milli,
            "attribution": "confounded" if confounded else "isolated",
            "recommendation": _recommendation(predicted, realized, round_surface, confounded),
        })
    pruned = [e["round"] for e in entries if e["recommendation"].startswith("prune")]
    return {
        "schema": "telemetry-contracts/feature-scorecard@1",
        "rubric": RUBRIC,
        "scope": "applied-changes-this-run",
        "is_repository_finding": False,
        "entries": entries,
        "rounds_recommended_for_prune": pruned,
        "note": (
            "maintenance self-assessment of this run's applied changes, not a "
            "finding about the analyzed repository"
        ),
    }
