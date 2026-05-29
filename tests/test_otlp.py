from pathlib import Path

from telemetry_contracts.otlp import load_otlp_json
from telemetry_contracts.validator import validate_events
from telemetry_contracts.loader import load_contract


ROOT = Path(__file__).resolve().parents[1]


def test_otlp_case_study_confirms_missing_tenant_bug():
    contract = load_contract(ROOT / "examples/real_world/otel_checkout_missing_tenant.contract.json")
    events = load_otlp_json(ROOT / "examples/real_world/otel_checkout_missing_tenant.otlp.json")

    findings = validate_events(contract, events)

    assert any(f.code == "telemetry.missing_field" and "tenant_id" in f.message for f in findings)
