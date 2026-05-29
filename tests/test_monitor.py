from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.monitor import format_monitor_markdown, run_compiled_monitor
from telemetry_contracts.validator import validate_events

ROOT = Path(__file__).resolve().parents[1]


def _codes(report):
    return {finding["code"] for finding in report["findings"]}


def test_compiled_monitor_matches_temporal_property_fixture_codes():
    contract = load_contract(ROOT / "examples/temporal_logic/contract.json")
    events = load_jsonl(ROOT / "examples/temporal_logic/failing.jsonl")

    report = run_compiled_monitor(contract, events)
    validator_codes = {finding.code for finding in validate_events(contract, events)}

    assert report["summary"]["pass"] is False
    assert _codes(report) == validator_codes
    assert report["summary"]["compiled_temporal_property_monitors"] == 5
    assert report["summary"]["max_pending_responses"] == 1
    assert "bounded-runtime-monitor-v1" in format_monitor_markdown(report)


def test_compiled_monitor_is_deterministic_on_historical_gitlab_fixture():
    contract = load_contract(ROOT / "case_studies/gitlab_2017_database_outage/contract.json")
    events = load_jsonl(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl")

    first = run_compiled_monitor(contract, events)
    second = run_compiled_monitor(contract, events)

    assert first == second
    assert first["summary"]["compiled_signal_monitors"] == 5
    assert first["summary"]["compiled_temporal_property_monitors"] == 2
    assert first["summary"]["findings_by_code"]["telemetry.temporal_response"] == 1
    assert first["summary"]["max_pending_responses"] == 1


def test_compiled_monitor_accepts_passing_checkout_trace():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    events = load_jsonl(ROOT / "examples/telemetry/passing.jsonl")

    report = run_compiled_monitor(contract, events)

    assert report["summary"]["pass"] is True
    assert report["findings"] == []
