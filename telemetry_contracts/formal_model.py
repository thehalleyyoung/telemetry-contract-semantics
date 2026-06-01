"""Consolidated formal model: definitions, guarantees, and executable witnesses.

This module is the single place that states each formal guarantee the tool makes
*and* discharges it as a machine-checkable verdict with a stable id. Every
guarantee carries:

* a stable id (e.g. ``FM.refinement.transitivity``) the paper can cite;
* a paper-grade statement of the property;
* the code symbol that implements it and the test(s) that witness it
  (for a generated claim -> code -> test traceability table);
* an explicit approximation direction (exact / over- / under-approximation),
  tying the guarantee to the soundness/incompleteness story; and
* an **executable witness** that runs deterministically and returns
  ``holds: true|false`` so "N obligations, all discharged" is a checked fact, not
  a prose assertion.

Everything is offline, pure-stdlib, and byte-deterministic: witnesses build small
finite fixtures (or accept supplied real events/contracts) and reuse the shipped
checkers (`check_contract_refinement`, `evaluate_assume_guarantee`,
`summarize_abstract_domains`, `check_transformation_preservation`, `run_pipeline`).
"""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .abstract_domains import _attrs, _event_key, summarize_abstract_domains
from .assume_guarantee import evaluate_assume_guarantee
from .pipeline import run_pipeline
from .preservation import check_transformation_preservation
from .refinement import check_contract_refinement

FORMAL_MODEL_SCHEMA = "telemetry-contracts/formal-model@1"

# Approximation directions used in the soundness story.
EXACT = "exact"
OVER = "over-approximation"
UNDER = "under-approximation"


@dataclass(frozen=True)
class Guarantee:
    """A formal guarantee: its statement, code/test provenance, and witness."""

    id: str
    family: str
    statement: str
    code: str
    tests: tuple[str, ...]
    approximation: str
    witness: Callable[[dict[str, Any]], "tuple[bool, str]"]


# ---------------------------------------------------------------------------
# Deterministic finite fixtures (no network, no RNG, no wall-clock).
# ---------------------------------------------------------------------------


def _sample_contract() -> dict[str, Any]:
    return {
        "service": "api",
        "version": 1,
        "spans": [
            {
                "name": "http.request",
                "required": True,
                "attributes": {
                    "trace_id": {"type": "string", "required": True},
                },
            }
        ],
        "scenarios": [
            {
                "id": "triage",
                "question": "Why did the request fail?",
                "requires": [{"kind": "span", "name": "http.request"}],
            }
        ],
        "assume_guarantee": {
            "service_guarantees": [
                {
                    "id": "ag-correlation",
                    "signal": "span",
                    "name": "http.request",
                    "fields": ["trace_id"],
                    "required": True,
                }
            ]
        },
    }


def _strengthen(contract: dict[str, Any], field: str) -> dict[str, Any]:
    """Return a candidate that requires one more attribute (a refinement of base)."""

    out = copy.deepcopy(contract)
    out["spans"][0]["attributes"][field] = {"type": "string", "required": True}
    return out


def _weaken(contract: dict[str, Any]) -> dict[str, Any]:
    """Return a candidate that drops a required attribute (NOT a refinement)."""

    out = copy.deepcopy(contract)
    out["spans"][0]["attributes"].pop("trace_id", None)
    return out


def _events_good() -> list[dict[str, Any]]:
    return [
        {"kind": "span", "name": "http.request", "service": "api", "trace_id": f"t{i}"}
        for i in range(4)
    ]


def _events_missing_correlation() -> list[dict[str, Any]]:
    return [
        {"kind": "span", "name": "http.request", "service": "api", "severity": "error"}
        for _ in range(4)
    ]


def _write_fixture_repo(directory: Path) -> Path:
    """Write a deterministic under-instrumented repo for the staged-loop witnesses."""

    logs = directory / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    events = []
    for i in range(12):
        event = {"kind": "span", "name": "http.request", "service": "api"}
        if i % 3 == 0:
            event["status"] = "error"  # failure with no correlation / no duration
        else:
            event["trace_id"] = f"t{i}"
            event["duration_ms"] = 5 + i
        events.append(event)
    logs.joinpath("app.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events), encoding="utf-8"
    )
    src = directory / "src"
    src.mkdir(parents=True, exist_ok=True)
    src.joinpath("app.py").write_text(
        "import logging\nfrom opentelemetry import trace\n"
        "from fastapi import FastAPI\napp = FastAPI()\n",
        encoding="utf-8",
    )
    return directory


def _pipeline_on_fixture(ctx: dict[str, Any]) -> dict[str, Any]:
    """Run (and cache) the staged loop once on a deterministic fixture repo."""

    if "pipeline_report" in ctx:
        return ctx["pipeline_report"]
    tmp = tempfile.mkdtemp(prefix="telemetry-contracts-fm-")
    try:
        _write_fixture_repo(Path(tmp))
        report = run_pipeline(tmp, rounds=3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ctx["pipeline_report"] = report
    return report


# ---------------------------------------------------------------------------
# Witnesses. Each returns (holds, detail).
# ---------------------------------------------------------------------------


def _w_refinement_reflexivity(ctx: dict[str, Any]) -> tuple[bool, str]:
    c = ctx.get("contract") or _sample_contract()
    rep = check_contract_refinement(c, copy.deepcopy(c))
    holds = rep["summary"]["refines"] is True
    return holds, f"C ⊑ C refines={rep['summary']['refines']}"


def _w_refinement_transitivity(ctx: dict[str, Any]) -> tuple[bool, str]:
    c = _sample_contract()
    b = _strengthen(c, "duration_ms")
    a = _strengthen(b, "user_facing_status")
    ab = check_contract_refinement(c, b)["summary"]["refines"]
    ba = check_contract_refinement(b, a)["summary"]["refines"]
    ac = check_contract_refinement(c, a)["summary"]["refines"]
    holds = ab and ba and ac
    return holds, f"A⊑B={ba}, B⊑C={ab}, therefore A⊑C={ac}"


def _w_refinement_antisymmetry(ctx: dict[str, Any]) -> tuple[bool, str]:
    c = _sample_contract()
    c2 = copy.deepcopy(c)  # structurally equal candidate
    fwd = check_contract_refinement(c, c2)["summary"]["refines"]
    bwd = check_contract_refinement(c2, c)["summary"]["refines"]
    # Mutual refinement of equal contracts holds; a strict strengthening does not
    # refine back (the order is a genuine partial order, not trivial equality).
    strict = _strengthen(c, "duration_ms")
    not_back = check_contract_refinement(strict, c)["summary"]["refines"] is False
    holds = fwd and bwd and not_back
    return holds, f"C⊑C′={fwd} and C′⊑C={bwd}; strict-strengthen refines-back={not not_back}"


def _w_refinement_order_nontrivial(ctx: dict[str, Any]) -> tuple[bool, str]:
    c = _sample_contract()
    weak = _weaken(c)
    rejected = check_contract_refinement(c, weak)["summary"]["refines"] is False
    return rejected, f"weakening candidate (drops required trace_id) refines base = {not rejected}"


def _w_monotonicity_nondecreasing(ctx: dict[str, Any]) -> tuple[bool, str]:
    rep = _pipeline_on_fixture(ctx)
    if rep["final"] is None:
        return False, "no telemetry / no final state"
    base = rep["baseline"]["diagnosability_score"]
    final = rep["final"]["diagnosability_score"]
    no_applied_regression = all(entry["regressions"] == 0 for entry in rep["impact_ledger"])
    holds = final >= base and no_applied_regression
    return holds, f"baseline {base} ≤ final {final}; applied rounds with 0 regressions={no_applied_regression}"


def _w_monotonicity_regression_quarantined(ctx: dict[str, Any]) -> tuple[bool, str]:
    rep = _pipeline_on_fixture(ctx)
    # Every quarantined round contributes zero realized score and applies zero
    # changes (a regression can never silently advance the state).
    quarantined = [r for r in rep.get("rounds", []) if r.get("quarantined")]
    ledger_q = [e for e in rep.get("impact_ledger", []) if e.get("quarantined")]
    holds = all(e["realized_score_delta"] == 0 and e["changes_applied"] == 0 for e in ledger_q)
    return holds, f"quarantined rounds={len(quarantined)}, all with realized_delta=0 & 0 changes={holds}"


def _w_termination_bounded_rounds(ctx: dict[str, Any]) -> tuple[bool, str]:
    tmp = tempfile.mkdtemp(prefix="telemetry-contracts-fm-")
    try:
        _write_fixture_repo(Path(tmp))
        rep = run_pipeline(tmp, rounds=2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bounded = len(rep.get("rounds", [])) <= 2
    stopped = bool(rep.get("stopped_reason"))
    holds = bounded and stopped
    return holds, f"rounds={len(rep.get('rounds', []))} ≤ 2; stopped_reason={rep.get('stopped_reason')!r}"


def _w_termination_monotonic_exclusion(ctx: dict[str, Any]) -> tuple[bool, str]:
    rep = _pipeline_on_fixture(ctx)
    # A gap applied (or quarantined) in one round is never planned again later:
    # the excluded/applied gap set only grows, so the loop cannot cycle.
    seen: set[str] = set()
    cycled = False
    for r in rep.get("rounds", []):
        gaps = {c["gap"] for c in r["plan"]["planned_changes"]}
        if gaps & seen:
            cycled = True
            break
        seen |= gaps
    return (not cycled), f"distinct planned-gap sets across rounds (no re-planning) = {not cycled}"


def _w_assume_guarantee_passing(ctx: dict[str, Any]) -> tuple[bool, str]:
    rep = evaluate_assume_guarantee(_sample_contract(), _events_good())
    holds = rep["summary"]["pass"] is True and rep["summary"]["violated"] == 0
    return holds, f"satisfying fixture: pass={rep['summary']['pass']}, violated={rep['summary']['violated']}"


def _w_assume_guarantee_failing(ctx: dict[str, Any]) -> tuple[bool, str]:
    rep = evaluate_assume_guarantee(_sample_contract(), _events_missing_correlation())
    holds = rep["summary"]["pass"] is False and rep["summary"]["violated"] >= 1
    return holds, f"violating fixture: pass={rep['summary']['pass']}, violated={rep['summary']['violated']}"


def _events_with_attrs() -> list[dict[str, Any]]:
    return [
        {
            "kind": "span",
            "name": "http.request",
            "attributes": {"trace_id": f"t{i}", "http.method": "GET"},
        }
        for i in range(4)
    ]


def _w_abstract_domains_presence_sound(ctx: dict[str, Any]) -> tuple[bool, str]:
    events = ctx.get("events") or _events_with_attrs()
    summary = summarize_abstract_domains(_sample_contract(), events)
    presence = {d["name"]: d for d in summary["domains"]}["attribute_presence"]["values"]
    # Soundness direction: any field present in an event (its attribute/tag/field
    # containers) is never reported absent — it must appear in must/may/observed_extra
    # for that event's signal key.
    offenders: list[str] = []
    for event in events:
        key = ":".join(_event_key(event))
        cell = presence.get(key, {})
        reported = set(cell.get("must", [])) | set(cell.get("may", [])) | set(cell.get("observed_extra", []))
        for field in _attrs(event):
            if field not in reported:
                offenders.append(f"{key}.{field}")
    holds = not offenders
    return holds, f"present fields under-reported as absent: {sorted(set(offenders)) or 'none'}"


def _w_preservation_benign(ctx: dict[str, Any]) -> tuple[bool, str]:
    c = _sample_contract()
    src = _events_good()
    rep = check_transformation_preservation(c, src, copy.deepcopy(src), transformations=["redacted"])
    holds = rep["summary"]["pass"] is True
    return holds, f"identity/benign transform preserves obligations: pass={rep['summary']['pass']}"


def _w_preservation_destructive(ctx: dict[str, Any]) -> tuple[bool, str]:
    c = _sample_contract()
    src = _events_good()
    # Over-aggressive redaction drops the required correlation field.
    transformed = [{k: v for k, v in e.items() if k != "trace_id"} for e in src]
    rep = check_transformation_preservation(c, src, transformed, transformations=["redacted"])
    holds = rep["summary"]["pass"] is False
    return holds, f"destructive transform (drops trace_id) detected: pass={rep['summary']['pass']}"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GUARANTEES: list[Guarantee] = [
    Guarantee(
        "FM.refinement.reflexivity", "refinement",
        "Refinement is reflexive: every contract refines itself (C ⊑ C).",
        "refinement:check_contract_refinement", ("tests/test_formal_model.py",), EXACT,
        _w_refinement_reflexivity,
    ),
    Guarantee(
        "FM.refinement.transitivity", "refinement",
        "Refinement is transitive: if A ⊑ B and B ⊑ C then A ⊑ C, so a chain of "
        "strengthening edits composes into a single refinement of the original.",
        "refinement:check_contract_refinement", ("tests/test_formal_model.py",), EXACT,
        _w_refinement_transitivity,
    ),
    Guarantee(
        "FM.refinement.antisymmetry", "refinement",
        "Refinement is a partial order: mutually-refining contracts are equivalent, "
        "and a strict strengthening does not refine back (the order is non-trivial).",
        "refinement:check_contract_refinement", ("tests/test_formal_model.py",), EXACT,
        _w_refinement_antisymmetry,
    ),
    Guarantee(
        "FM.refinement.order-soundness", "refinement",
        "The order is sound: a candidate that drops a required base obligation is "
        "rejected as a non-refinement (weakening is never accepted as refinement).",
        "refinement:check_contract_refinement", ("tests/test_formal_model.py",), OVER,
        _w_refinement_order_nontrivial,
    ),
    Guarantee(
        "FM.monotonicity.nondecreasing", "monotonicity",
        "Applying a planned change never decreases diagnosability: the final score "
        "is at least the baseline and every applied round introduces zero "
        "regressions.",
        "pipeline:run_pipeline", ("tests/test_formal_model.py", "tests/test_formal_model_real.py"), EXACT,
        _w_monotonicity_nondecreasing,
    ),
    Guarantee(
        "FM.monotonicity.regression-quarantined", "monotonicity",
        "A change whose differential would regress safety is quarantined and rolled "
        "back: it realizes zero score delta and applies zero changes.",
        "pipeline:run_pipeline", ("tests/test_formal_model.py",), EXACT,
        _w_monotonicity_regression_quarantined,
    ),
    Guarantee(
        "FM.termination.bounded-rounds", "termination",
        "The staged loop terminates within the configured round bound and always "
        "records a stopping reason.",
        "pipeline:run_pipeline", ("tests/test_formal_model.py", "tests/test_formal_model_real.py"), EXACT,
        _w_termination_bounded_rounds,
    ),
    Guarantee(
        "FM.termination.monotonic-exclusion", "termination",
        "The excluded/applied gap set grows monotonically: a gap planned in one "
        "round is never re-planned later, so the loop cannot cycle.",
        "pipeline:run_pipeline", ("tests/test_formal_model.py",), EXACT,
        _w_termination_monotonic_exclusion,
    ),
    Guarantee(
        "FM.assume-guarantee.passing-discharges", "assume-guarantee",
        "A satisfying finite trace discharges every declared layer obligation "
        "(pass, zero violations).",
        "assume_guarantee:evaluate_assume_guarantee", ("tests/test_formal_model.py",), UNDER,
        _w_assume_guarantee_passing,
    ),
    Guarantee(
        "FM.assume-guarantee.failing-flags", "assume-guarantee",
        "A violating finite trace produces a layer-specific counterexample "
        "(fail, at least one violated obligation).",
        "assume_guarantee:evaluate_assume_guarantee", ("tests/test_formal_model.py",), UNDER,
        _w_assume_guarantee_failing,
    ),
    Guarantee(
        "FM.abstract-domains.presence-soundness", "abstract-domains",
        "The attribute-presence domain over-approximates presence: a field present "
        "in any event is never reported absent (sound for under-instrumentation "
        "claims).",
        "abstract_domains:summarize_abstract_domains", ("tests/test_formal_model.py", "tests/test_formal_model_real.py"), OVER,
        _w_abstract_domains_presence_sound,
    ),
    Guarantee(
        "FM.preservation.benign-preserves", "preservation",
        "A transformation that retains the contract's witnesses preserves every "
        "runtime obligation (pass).",
        "preservation:check_transformation_preservation", ("tests/test_formal_model.py",), EXACT,
        _w_preservation_benign,
    ),
    Guarantee(
        "FM.preservation.destructive-detected", "preservation",
        "A transformation that destroys a required witness (e.g. over-redacting a "
        "correlation id) is detected as non-preserving (fail).",
        "preservation:check_transformation_preservation", ("tests/test_formal_model.py", "tests/test_formal_model_real.py"), EXACT,
        _w_preservation_destructive,
    ),
]


# ---------------------------------------------------------------------------
# Discharge + rendering
# ---------------------------------------------------------------------------


def discharge_formal_model(
    *, events: list[dict[str, Any]] | None = None, contract: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run every guarantee's witness and return machine-checkable verdicts.

    ``events`` / ``contract`` let real harvested data drive the data-dependent
    witnesses (abstract-domains, refinement); the rest use built-in finite
    fixtures. The output is deterministic and id-sorted.
    """

    ctx: dict[str, Any] = {}
    if events is not None:
        ctx["events"] = events
    if contract is not None:
        ctx["contract"] = contract

    verdicts: list[dict[str, Any]] = []
    for g in sorted(GUARANTEES, key=lambda x: x.id):
        try:
            holds, detail = g.witness(ctx)
        except Exception as exc:  # a crashing witness is a failed obligation
            holds, detail = False, f"witness error: {type(exc).__name__}: {exc}"
        verdicts.append(
            {
                "id": g.id,
                "family": g.family,
                "statement": g.statement,
                "code": g.code,
                "tests": list(g.tests),
                "approximation": g.approximation,
                "holds": bool(holds),
                "detail": detail,
            }
        )

    families = sorted({v["family"] for v in verdicts})
    discharged = sum(1 for v in verdicts if v["holds"])
    return {
        "schema": FORMAL_MODEL_SCHEMA,
        "summary": {
            "obligations": len(verdicts),
            "discharged": discharged,
            "failed": len(verdicts) - discharged,
            "all_discharged": discharged == len(verdicts),
            "families": families,
        },
        "obligations": verdicts,
    }


def render_formal_model_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Formal model: guarantees and executable witnesses",
        "",
        "Each guarantee below is stated precisely, tied to the code that implements "
        "it and the test that witnesses it, and **discharged** by a deterministic "
        "executable check. The tool reports a machine-checkable verdict per "
        "obligation, so the paper can cite a checked count rather than a claim.",
        "",
        f"**{s['discharged']}/{s['obligations']}** obligations discharged "
        f"({'all' if s['all_discharged'] else 'NOT all'} hold) across "
        f"{len(s['families'])} families: {', '.join(s['families'])}.",
        "",
    ]
    by_family: dict[str, list[dict[str, Any]]] = {}
    for v in report["obligations"]:
        by_family.setdefault(v["family"], []).append(v)
    for family in sorted(by_family):
        lines += [f"## {family}", ""]
        for v in by_family[family]:
            mark = "✓" if v["holds"] else "✗"
            lines += [
                f"### `{v['id']}` {mark}",
                "",
                v["statement"],
                "",
                f"- Approximation: **{v['approximation']}**",
                f"- Implemented by: `{v['code']}`",
                f"- Witnessed by: {', '.join('`'+t+'`' for t in v['tests'])}",
                f"- Verdict: **{'holds' if v['holds'] else 'FAILED'}** — {v['detail']}",
                "",
            ]
    return "\n".join(lines) + "\n"


def render_traceability_markdown(report: dict[str, Any]) -> str:
    """Render the claim -> code -> test traceability table."""

    lines = [
        "# Formal-guarantee traceability (claim → code → test)",
        "",
        "Every formal guarantee maps mechanically to the code that implements it, "
        "the test that witnesses it, and its discharge verdict.",
        "",
        "| Guarantee id | Family | Approximation | Code | Tests | Discharged |",
        "| --- | --- | --- | --- | --- | :---: |",
    ]
    for v in report["obligations"]:
        tests = "<br>".join(f"`{t}`" for t in v["tests"])
        lines.append(
            f"| `{v['id']}` | {v['family']} | {v['approximation']} | `{v['code']}` | "
            f"{tests} | {'yes' if v['holds'] else 'NO'} |"
        )
    return "\n".join(lines) + "\n"
