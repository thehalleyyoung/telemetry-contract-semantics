import json
from pathlib import Path

from telemetry_contracts.cli import main
from telemetry_contracts.sarif import report_to_sarif

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / "examples/ci/static_findings.example.json"


def test_sarif_maps_findings_to_rules_and_locations(capsys):
    report = report_to_sarif(json.loads(FINDINGS.read_text()))
    run = report["runs"][0]
    assert report["version"] == "2.1.0"
    assert {rule["id"] for rule in run["tool"]["driver"]["rules"]} == {"static.secret_logging", "static.unbounded_label"}
    result = run["results"][0]
    assert result["ruleId"] == "static.secret_logging"
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 6
    assert main(["sarif", "--findings", str(FINDINGS)]) == 0
    output = capsys.readouterr().out
    assert '"version": "2.1.0"' in output


def test_validate_format_sarif(capsys):
    code = main([
        "validate",
        "--contract",
        str(ROOT / "examples/contracts/checkout.contract.json"),
        "--events",
        str(ROOT / "examples/telemetry/failing.jsonl"),
        "--format",
        "sarif",
    ])
    output = capsys.readouterr().out
    assert code == 1
    assert '"ruleId": "telemetry.allowed_values"' in output
