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


def test_static_checker_reports_secret_logging_with_location():
    source = ROOT / "case_studies/current/owasp_securetea_signin/Signin.js"
    findings = check_sources({"service": "securetea", "static_expectations": {"spans": [], "metrics": [], "logs": []}}, [source])
    secret_findings = [item for item in findings if item.code == "static.secret_logging"]
    assert [item.path.split(":")[-1] for item in secret_findings] == ["27", "48"]
    assert all(item.severity == "error" for item in secret_findings)
