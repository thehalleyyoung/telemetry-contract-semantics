"""Offline proof that every formal guarantee is discharged by its witness.

The formal model registers a fixed set of guarantees (refinement order,
monotonicity, termination, assume-guarantee, abstract-domain soundness,
transformation preservation). Each one carries a deterministic executable
witness over a built-in finite fixture, so the paper can cite a *checked* count
rather than a prose claim. These tests lock that all obligations discharge,
that the output is deterministic, and that the renderers expose every id.
"""

from __future__ import annotations

import json

from telemetry_contracts.formal_model import (
    GUARANTEES,
    discharge_formal_model,
    render_formal_model_markdown,
    render_traceability_markdown,
)

EXPECTED_FAMILIES = {
    "abstract-domains",
    "assume-guarantee",
    "monotonicity",
    "preservation",
    "refinement",
    "termination",
}


def test_all_obligations_discharged():
    report = discharge_formal_model()
    s = report["summary"]
    assert s["all_discharged"] is True, [
        (v["id"], v["detail"]) for v in report["obligations"] if not v["holds"]
    ]
    assert s["failed"] == 0
    assert s["obligations"] == len(GUARANTEES)
    assert s["discharged"] == len(GUARANTEES)


def test_registry_is_well_formed():
    ids = [g.id for g in GUARANTEES]
    assert len(ids) == len(set(ids)), "duplicate guarantee ids"
    assert set(g.family for g in GUARANTEES) == EXPECTED_FAMILIES
    for g in GUARANTEES:
        assert g.id.startswith("FM.")
        assert g.statement.strip()
        assert g.code and ":" in g.code
        assert g.tests, f"{g.id} cites no test"
        assert g.approximation in {"exact", "over-approximation", "under-approximation"}


def test_obligations_are_id_sorted():
    report = discharge_formal_model()
    ids = [v["id"] for v in report["obligations"]]
    assert ids == sorted(ids)


def test_discharge_is_deterministic():
    a = json.dumps(discharge_formal_model(), sort_keys=True)
    b = json.dumps(discharge_formal_model(), sort_keys=True)
    assert a == b


def test_summary_counts_are_consistent():
    report = discharge_formal_model()
    holds = sum(1 for v in report["obligations"] if v["holds"])
    assert report["summary"]["discharged"] == holds
    assert report["summary"]["failed"] == report["summary"]["obligations"] - holds


def test_each_family_has_at_least_one_obligation():
    report = discharge_formal_model()
    seen = {v["family"] for v in report["obligations"]}
    assert seen == EXPECTED_FAMILIES


def test_refinement_order_axioms_are_witnessed():
    report = discharge_formal_model()
    ids = {v["id"]: v for v in report["obligations"]}
    for axiom in (
        "FM.refinement.reflexivity",
        "FM.refinement.transitivity",
        "FM.refinement.antisymmetry",
        "FM.refinement.order-soundness",
    ):
        assert ids[axiom]["holds"], (axiom, ids[axiom]["detail"])


def test_markdown_renderer_lists_every_id():
    report = discharge_formal_model()
    md = render_formal_model_markdown(report)
    assert md.startswith("# Formal model")
    assert f"{len(GUARANTEES)}/{len(GUARANTEES)}" in md
    for v in report["obligations"]:
        assert f"`{v['id']}`" in md
        assert v["statement"] in md


def test_traceability_renderer_is_a_table_with_every_id():
    report = discharge_formal_model()
    md = render_traceability_markdown(report)
    assert "| Guarantee id |" in md
    for v in report["obligations"]:
        assert f"`{v['id']}`" in md
        assert f"`{v['code']}`" in md
    # All discharged -> no "NO" cells in the Discharged column.
    assert "| NO |" not in md


def test_renderers_are_deterministic():
    r1 = discharge_formal_model()
    r2 = discharge_formal_model()
    assert render_formal_model_markdown(r1) == render_formal_model_markdown(r2)
    assert render_traceability_markdown(r1) == render_traceability_markdown(r2)


def test_events_argument_drives_data_dependent_witnesses():
    # Passing real-shaped events with attribute containers must still discharge
    # the presence-soundness obligation (present fields never reported absent).
    events = [
        {"kind": "span", "name": "http.request", "attributes": {"trace_id": "t1", "http.method": "GET"}},
        {"kind": "span", "name": "http.request", "attributes": {"trace_id": "t2"}},
    ]
    report = discharge_formal_model(events=events)
    ids = {v["id"]: v for v in report["obligations"]}
    assert ids["FM.abstract-domains.presence-soundness"]["holds"]
