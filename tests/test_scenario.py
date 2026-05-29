from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.scenario import check_scenario, choose_scenario, evaluate_scenario_adequacy

ROOT = Path(__file__).resolve().parents[1]


def test_scenario_passes_for_complete_telemetry():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    scenario = choose_scenario(contract, scenario_id="payment-timeout")
    assert check_scenario(contract, load_jsonl(ROOT / "examples/telemetry/passing.jsonl"), scenario) == []


def test_scenario_question_matching_and_missing_fields():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    scenario = choose_scenario(contract, question="diagnose payment timeout")
    findings = check_scenario(contract, load_jsonl(ROOT / "examples/telemetry/failing.jsonl"), scenario)
    assert {finding.code for finding in findings} >= {"scenario.missing_field", "scenario.missing_signal"}


def test_scenario_adequacy_reports_minimum_observation_witnesses():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    scenario = choose_scenario(contract, scenario_id="payment-timeout")
    report = evaluate_scenario_adequacy(contract, load_jsonl(ROOT / "examples/telemetry/failing.jsonl"), scenario)
    assert report["model"]["name"] == "diagnosability-adequacy-v1"
    assert report["answerable"] is False
    assert [item["status"] for item in report["minimum_observations"]] == ["missing-fields", "satisfied", "missing-signal"]
    assert report["minimum_observations"][0]["matching_event_indices"] == [1]
    assert report["minimum_observations"][2]["missing"][0]["details"]["minimum_observation"]["signal"] == "metric"
