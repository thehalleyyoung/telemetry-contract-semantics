from pathlib import Path

from telemetry_contracts import (
    check_sources,
    generate_incident_readiness_report,
    generate_service_owner_report,
    import_otlp,
    load_contract,
    load_jsonl,
    run_compiled_monitor,
    run_benchmark,
    validate_events,
)

ROOT = Path(__file__).resolve().parents[1]


def test_public_api_embedding_smoke():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    events = load_jsonl(ROOT / "examples/telemetry/passing.jsonl")
    assert validate_events(contract, events) == []
    assert check_sources(contract, [ROOT / "examples/services"]) == []
    readiness = generate_incident_readiness_report(contract, events, ["payment-timeout"])
    assert readiness["summary"]["pass"] is True
    owner = generate_service_owner_report(contract, events, [ROOT / "examples/services"], ["payment-timeout"])
    assert owner["summary"]["pass"] is True
    monitor = run_compiled_monitor(contract, events)
    assert monitor["summary"]["events"] == len(events)
    benchmark = run_benchmark(ROOT / "benchmarks/builtin.json", filters={"case_id": ["checkout-payment-timeout-pass"]})
    assert benchmark["summary"]["cases"] == 1
    imported = import_otlp(ROOT / "examples/otlp/collector_mixed_signals.otlp.json")
    assert imported["summary"]["events"] > 0
