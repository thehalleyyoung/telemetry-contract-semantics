from pathlib import Path

from telemetry_contracts.loader import load_contract
from telemetry_contracts.static_checker import check_sources

ROOT = Path(__file__).resolve().parents[1]


def test_static_checker_finds_example_instrumentation():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    assert check_sources(contract, [ROOT / "examples/services"]) == []


def test_static_checker_reports_missing_name():
    source = ROOT / "tests/fixtures/no_instrumentation.py"
    findings = check_sources({"service": "svc", "spans": [{"name": "important.span"}]}, [source])
    assert findings[0].code == "static.missing_instrumentation"
