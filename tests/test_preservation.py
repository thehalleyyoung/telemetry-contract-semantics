from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.preservation import check_transformation_preservation, format_preservation_markdown

ROOT = Path(__file__).resolve().parents[1]
GITLAB = ROOT / "case_studies/gitlab_2017_database_outage"


def test_transformation_preservation_accepts_reordered_trace():
    contract = load_contract(str(GITLAB / "contract.json"))
    source = load_jsonl(str(GITLAB / "reconstructed_events.jsonl"))

    report = check_transformation_preservation(contract, source, list(reversed(source)), ["sampling"], ["restore-readiness"])

    assert report["summary"]["pass"] is True
    assert report["summary"]["preservation_findings"] == 0
    assert "transformation-preservation-v1" in format_preservation_markdown(report)


def test_transformation_preservation_reports_sampled_missing_historical_witness():
    contract = load_contract(str(GITLAB / "contract.json"))
    source = load_jsonl(str(GITLAB / "reconstructed_events.jsonl"))
    sampled = load_jsonl(str(GITLAB / "reconstructed_events_sampled_missing_alert.jsonl"))

    report = check_transformation_preservation(contract, source, sampled, ["sampling"], ["restore-readiness"])

    assert report["summary"]["pass"] is False
    assert report["summary"]["preservation_findings"] >= 1
    codes = {finding["code"] for finding in report["findings"]}
    assert "preservation.contract_obligation" in codes
    assert "preservation.scenario_signal" in codes
    assert any("backup.pg_dump.failed" in finding["message"] for finding in report["findings"])


def test_transformation_preservation_uses_contract_metadata_defaults():
    contract = load_contract(str(GITLAB / "contract.json"))
    source = load_jsonl(str(GITLAB / "reconstructed_events.jsonl"))
    sampled = load_jsonl(str(GITLAB / "reconstructed_events_sampled_missing_alert.jsonl"))

    report = check_transformation_preservation(contract, source, sampled)

    assert report["approved_transformations"] == ["sampling"]
    assert report["summary"]["scenarios_checked"] == 1
