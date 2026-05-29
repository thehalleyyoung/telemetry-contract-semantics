import ast
from pathlib import Path

from telemetry_contracts.findings import TAXONOMY, Finding
from telemetry_contracts.semantics import OBSERVATION_DOMAIN, describe_model, format_model_markdown


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
    assert "Satisfaction" in format_model_markdown(report)


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
