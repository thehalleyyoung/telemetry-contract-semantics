import json
from pathlib import Path

from telemetry_contracts.alternatives import evaluate_alternative_obligations, format_alternative_obligations_markdown
from telemetry_contracts.cli import main
from telemetry_contracts.scenario import check_scenario, evaluate_scenario_adequacy
from telemetry_contracts.validator import validate_contract_shape, validate_events

ROOT = Path(__file__).resolve().parents[1]


def _contract(required=True):
    return {
        "version": "1.0",
        "service": "svc",
        "alternative_obligations": [
            {
                "id": "error-location-evidence",
                "purpose": "Either a log or a span can identify the failed shard.",
                "required": required,
                "any_of": [
                    {"id": "log", "signal": "log", "name": "svc.error", "fields": ["shard", "tenant"]},
                    {"id": "span", "signal": "span", "name": "svc.error", "fields": ["shard", "tenant"]},
                ],
            }
        ],
    }


def test_alternative_obligation_accepts_one_witness_without_duplicate_missing_signal():
    events = [{"kind": "log", "service": "svc", "name": "svc.error", "fields": {"shard": "db-1", "tenant": "tenant-a"}}]

    findings = validate_events(_contract(), events)
    report = evaluate_alternative_obligations(_contract(), events)

    assert findings == []
    assert report["summary"] == {"groups": 1, "required_groups": 1, "satisfied_groups": 1, "unsatisfied_required_groups": 0, "pass": True}
    assert report["alternative_obligations"][0]["winning_option"] == "log"
    assert report["alternative_obligations"][0]["options"][1]["status"] == "missing-signal"


def test_alternative_obligation_reports_single_disjunction_failure():
    events = [{"kind": "log", "service": "svc", "name": "svc.error", "fields": {"shard": "db-1"}}]

    findings = validate_events(_contract(), events)

    assert [finding.code for finding in findings] == ["telemetry.alternative_missing"]
    assert findings[0].details["model"] == "alternative-obligations-v1"
    assert {option["status"] for option in findings[0].details["options"]} == {"missing-fields", "missing-signal"}


def test_optional_alternative_documents_path_without_failure():
    report = evaluate_alternative_obligations(_contract(required=False), [])
    findings = validate_events(_contract(required=False), [])

    assert findings == []
    assert report["summary"]["pass"] is True
    assert report["alternative_obligations"][0]["satisfied"] is False


def test_alternative_obligation_shape_linting():
    contract = {"version": "1.0", "service": "svc", "alternative_obligations": [{"id": "bad", "any_of": []}]}
    findings = validate_contract_shape(contract)

    assert "contract.alternative_obligation" in {finding.code for finding in findings}


def test_scenario_alternative_observation_has_single_finding():
    contract = _contract()
    scenario = {
        "id": "debug",
        "minimum_observations": [
            {
                "id": "error-location-evidence",
                "any_of": [
                    {"id": "log", "signal": "log", "name": "svc.error", "fields": ["shard", "tenant"]},
                    {"id": "span", "signal": "span", "name": "svc.error", "fields": ["shard", "tenant"]},
                ],
            }
        ],
    }

    findings = check_scenario(contract, [], scenario)
    report = evaluate_scenario_adequacy(contract, [], scenario)

    assert [finding.code for finding in findings] == ["scenario.alternative_missing"]
    assert report["minimum_observations"][0]["status"] == "unsatisfied"
    assert len(report["minimum_observations"][0]["options"]) == 2


def test_cli_alternative_obligations_report_on_gitlab_case_study(capsys):
    code = main(
        [
            "report",
            "alternative-obligations",
            "--contract",
            str(ROOT / "case_studies/gitlab_2017_database_outage/contract.json"),
            "--events",
            str(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl"),
            "--format",
            "json",
        ]
    )
    data = json.loads(capsys.readouterr().out)

    assert code == 0
    assert data["summary"]["pass"] is True
    assert data["alternative_obligations"][0]["winning_option"] == "structured-log"
    assert data["alternative_obligations"][0]["options"][1]["status"] == "missing-signal"


def test_markdown_report_explains_disjunction_semantics():
    report = evaluate_alternative_obligations(_contract(), [{"kind": "log", "service": "svc", "name": "svc.error", "fields": {"shard": "db-1", "tenant": "tenant-a"}}])
    markdown = format_alternative_obligations_markdown({key: value for key, value in report.items() if key != "raw_findings"})

    assert "finite disjunction" in markdown
    assert "Winning option: `log`" in markdown
