import ast
from pathlib import Path

from telemetry_contracts.findings import TAXONOMY, Finding
from telemetry_contracts.semantics import OBSERVATION_DOMAIN, build_event_structure, describe_model, format_model_markdown


ROOT = Path(__file__).resolve().parents[1]


def test_observation_domain_covers_core_objects():
    objects = {item["object"] for item in OBSERVATION_DOMAIN}

    assert {"span", "log", "metric", "resource", "scope", "exemplar", "timestamp", "attribute", "provenance"} <= objects


def test_describe_model_summarizes_events():
    report = describe_model(
        [
            {"kind": "span", "service": "svc", "name": "request", "trace_id": "t1", "attributes": {"tenant_id": "tenant-a"}},
            {"kind": "log", "service": "svc", "name": "failed", "fields": {"request_id": "r1"}},
        ]
    )

    assert report["satisfaction_relation"]["notation"] == "T ⊨ C"
    assert report["observed_artifact"]["counts_by_kind"] == {"log": 1, "span": 1}
    assert report["observed_artifact"]["correlation_key_counts"] == {"trace_id": 1}
    assert "tenant_id" in report["observed_artifact"]["fields_by_kind"]["span"]
    assert report["event_structure"]["model"] == "finite-event-structure"
    assert "Satisfaction" in format_model_markdown(report)
    assert "Incident-window event-structure diagrams" in format_model_markdown(report)


def test_event_structure_models_causality_attachments_exemplars_and_concurrency():
    events = [
        {"kind": "span", "name": "root", "trace_id": "t1", "span_id": "s0", "timestamp_ms": 0, "end_time_ms": 100},
        {"kind": "span", "name": "child", "trace_id": "t1", "span_id": "s1", "parent_span_id": "s0", "timestamp_ms": 10, "end_time_ms": 60},
        {"kind": "span", "name": "linked", "trace_id": "t1", "span_id": "s2", "links": [{"trace_id": "t1", "span_id": "s1"}], "timestamp_ms": 20, "end_time_ms": 50},
        {"kind": "span", "name": "parallel", "trace_id": "t1", "span_id": "s3", "timestamp_ms": 30, "end_time_ms": 55},
        {"kind": "log", "name": "child.failed", "trace_id": "t1", "span_id": "s1", "timestamp_ms": 70},
        {"kind": "metric", "name": "latency", "trace_id": "t1", "timestamp_ms": 80, "exemplars": [{"trace_id": "t1", "span_id": "s1"}]},
    ]

    structure = build_event_structure(events)
    relations = {(edge["from"], edge["to"], edge["relation"]) for edge in structure["edges"]}

    assert ("e0", "e1", "parent-child") in relations
    assert ("e1", "e2", "span-link") in relations
    assert ("e1", "e4", "log-attachment") in relations
    assert ("e1", "e5", "metric-exemplar") in relations
    assert any(edge["relation"] == "happens-before" for edge in structure["edges"])
    assert {"left": "e1", "right": "e3", "relation": "concurrent"} in structure["concurrency"]
    assert "flowchart TD" in structure["diagrams"][0]["mermaid"]


def test_finding_taxonomy_attaches_formal_clauses_to_json_findings():
    required = {"category", "default_severity", "formal_clause", "remediation", "disclosure_sensitivity", "service_owner", "sarif_level"}
    for code, entry in TAXONOMY.items():
        assert required <= set(entry), code

    finding = Finding("error", "telemetry.missing_field", "tenant_id missing", "event[0]").to_dict()

    assert finding["formal_clause"] == "SAT.required-field"
    assert finding["sarif_level"] == "error"


def test_all_static_finding_codes_have_taxonomy_entries():
    emitted_codes = set()
    for path in (ROOT / "telemetry_contracts").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", "")) == "Finding":
                if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    emitted_codes.add(node.args[1].value)

    assert emitted_codes <= set(TAXONOMY)
