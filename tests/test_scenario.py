from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.scenario import check_scenario, choose_scenario

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
