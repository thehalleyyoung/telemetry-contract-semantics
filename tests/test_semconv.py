from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.semconv import lint_semantic_conventions

ROOT = Path(__file__).resolve().parents[1]


def codes(report):
    return {finding["code"] for finding in report["findings"]}


def test_semconv_lints_legacy_http_attributes_with_exact_remediation():
    contract = {
        "version": "1.0",
        "service": "web",
        "spans": [
            {
                "name": "http.server.request",
                "attributes": {
                    "http.method": {"type": "string"},
                    "http.status_code": {"type": "integer"},
                },
            }
        ],
    }

    report = lint_semantic_conventions(contract, [])

    assert "semconv.legacy_attribute" in codes(report)
    assert "semconv.missing_attribute" in codes(report)
    legacy = [item for item in report["findings"] if item["code"] == "semconv.legacy_attribute"]
    assert any(item["details"]["expected_attribute"] == "http.request.method" for item in legacy)
    assert any("OpenTelemetry HTTP semantic conventions" in item["details"]["convention"] for item in legacy)


def test_semconv_lints_gitlab_historical_reconstruction_local_db_policy():
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    report = lint_semantic_conventions(load_contract(case / "contract.json"), load_jsonl(case / "reconstructed_events.jsonl"))

    assert "semconv.local_policy" in codes(report)
    assert "semconv.metric_unit" in codes(report)
    assert any(
        item.get("event_index") == 1 and item["details"]["attribute"] == "db.system.name"
        for item in report["findings"]
        if item["code"] == "semconv.local_policy"
    )
