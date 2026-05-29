import random
from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.monitor import run_compiled_monitor
from telemetry_contracts.otlp import load_otlp_json_detailed, load_otlp_jsonl_detailed
from telemetry_contracts.validator import validate_events

ROOT = Path(__file__).resolve().parents[1]


def test_microservice_contracts_ignore_unrelated_service_noise_property():
    events = load_jsonl(ROOT / "examples/microservices/events.jsonl")
    unrelated = {
        "kind": "log",
        "service": "unmodeled-noise",
        "name": "noise.missing_everything",
        "severity": "ERROR",
        "fields": {},
    }

    for contract_path in sorted((ROOT / "examples/microservices/contracts").glob("*.contract.json")):
        contract = load_contract(contract_path)
        assert validate_events(contract, events) == []
        assert validate_events(contract, [unrelated, *events]) == []


def test_microservice_correlation_property_detects_each_service_log_without_trace_id():
    events = load_jsonl(ROOT / "examples/microservices/events.jsonl")

    for contract_path in sorted((ROOT / "examples/microservices/contracts").glob("*.contract.json")):
        contract = load_contract(contract_path)
        service = contract["service"]
        mutated = []
        for event in events:
            copied = dict(event)
            if event.get("service") == service and event.get("kind") == "log":
                copied.pop("trace_id", None)
                copied.pop("request_id", None)
                copied["fields"] = {k: v for k, v in copied.get("fields", {}).items() if k not in {"trace_id", "request_id"}}
            mutated.append(copied)
        findings = validate_events(contract, mutated)
        assert any(f.code == "telemetry.correlation_missing" and f.event_index for f in findings), service


def test_microservice_randomized_trace_noise_and_correlation_mutations():
    events = load_jsonl(ROOT / "examples/microservices/events.jsonl")
    contracts = [load_contract(path) for path in sorted((ROOT / "examples/microservices/contracts").glob("*.contract.json"))]
    rng = random.Random(20250214)

    for _ in range(25):
        sampled = [dict(event) for event in events]
        rng.shuffle(sampled)
        for idx in range(rng.randint(0, 3)):
            sampled.insert(
                rng.randrange(len(sampled) + 1),
                {
                    "kind": rng.choice(["span", "log", "metric"]),
                    "service": f"unmodeled-noise-{idx}",
                    "name": f"noise.{idx}",
                    "fields": {"iteration": idx},
                },
            )
        for contract in contracts:
            assert validate_events(contract, sampled) == []

        target = rng.choice(contracts)
        mutated = []
        for event in sampled:
            copied = dict(event)
            if event.get("service") == target["service"] and event.get("kind") == "log":
                copied.pop("trace_id", None)
                copied.pop("request_id", None)
                copied["fields"] = {k: v for k, v in copied.get("fields", {}).items() if k not in {"trace_id", "request_id"}}
            mutated.append(copied)
        findings = validate_events(target, mutated)
        assert any(f.code == "telemetry.correlation_missing" for f in findings), target["service"]


def test_temporal_monitor_validator_differential_codes_agree_on_reconstructed_outage():
    contract = load_contract(ROOT / "case_studies/gitlab_2017_database_outage/contract.json")
    events = load_jsonl(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl")

    validator_codes = {f.code for f in validate_events(contract, events)}
    monitor = run_compiled_monitor(contract, events)
    monitor_codes = {item["code"] for item in monitor["findings"]}

    assert "telemetry.temporal_response" in validator_codes
    assert monitor_codes <= validator_codes
    assert monitor["summary"]["findings_by_code"]["telemetry.temporal_response"] == 1


def test_otlp_json_and_jsonl_diagnostics_have_consistent_invalidating_semantics():
    json_report = load_otlp_json_detailed(ROOT / "examples/otlp/collector_coverage_all_signals.otlp.json")
    jsonl_report = load_otlp_jsonl_detailed(ROOT / "examples/otlp/collector_malformed_records.otlp.jsonl")

    assert json_report["summary"]["invalidating_diagnostics"] == 3
    assert json_report["summary"]["diagnostics_by_code"]["otlp.dropped_evidence"] == 2
    assert jsonl_report["summary"]["invalidating_diagnostics"] == 3
    assert jsonl_report["summary"]["diagnostics_by_code"] == {"otlp.malformed_record": 2, "otlp.skipped_record": 1}
