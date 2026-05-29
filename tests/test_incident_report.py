from pathlib import Path

from telemetry_contracts.cli import main
from telemetry_contracts.incident_report import format_incident_readiness_markdown, generate_incident_readiness_report
from telemetry_contracts.loader import load_contract, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_CONTRACT = ROOT / "case_studies/gitlab_2017_database_outage/contract.json"
HISTORICAL_EVENTS = ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl"
CHECKOUT_CONTRACT = ROOT / "examples/contracts/checkout.contract.json"
CHECKOUT_EVENTS = ROOT / "examples/telemetry/passing.jsonl"


def test_incident_readiness_report_scores_historical_missing_evidence():
    report = generate_incident_readiness_report(load_contract(HISTORICAL_CONTRACT), load_jsonl(HISTORICAL_EVENTS))
    assert report["service"] == "gitlab.com-database"
    assert report["summary"]["pass"] is False
    assert report["summary"]["findings_by_code"]["scenario.missing_field"] == 3
    assert report["coverage"]["required_evidence"]["failed"] == 3
    assert report["coverage"]["remediation"]["score"] == 100
    assert report["unanswered_questions"][0]["id"] == "restore-readiness"
    assert len(report["unanswered_questions"][0]["missing_evidence"]) == 3
    markdown = format_incident_readiness_markdown(report)
    assert "Incident-readiness report: gitlab.com-database" in markdown
    assert "restore-readiness" in markdown
    assert "Top remediations" in markdown


def test_incident_readiness_cli_outputs_json_and_respects_fail_on(capsys):
    code = main([
        "report",
        "incident-readiness",
        "--contract",
        str(HISTORICAL_CONTRACT),
        "--events",
        str(HISTORICAL_EVENTS),
        "--fail-on",
        "never",
    ])
    output = capsys.readouterr().out
    assert code == 0
    assert '"incident_readiness_score"' in output
    assert '"scenario.missing_field": 3' in output


def test_incident_readiness_report_passes_checkout_fixture(capsys):
    assert main([
        "report",
        "incident-readiness",
        "--contract",
        str(CHECKOUT_CONTRACT),
        "--events",
        str(CHECKOUT_EVENTS),
        "--format",
        "markdown",
    ]) == 0
    output = capsys.readouterr().out
    assert "All declared incident questions are answerable" in output
