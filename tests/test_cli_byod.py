import json
from pathlib import Path

from telemetry_contracts.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/byod/app_logs.jsonl"


def test_analyze_command_text(capsys):
    code = main(["analyze", "--events", str(FIXTURE), "--fail-on", "never"])
    out = capsys.readouterr().out
    assert code == 0
    assert "no contract" in out
    assert "telemetry.sensitive_value" in out


def test_analyze_command_json_and_fail_on(capsys):
    code = main(["analyze", "--events", str(FIXTURE), "--format", "json", "--fail-on", "error"])
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["schema"] == "telemetry-contracts/discovery@1"
    assert data["input"]["format"] == "jsonl"
    assert code == 1  # raw email/bearer present -> error -> nonzero exit


def test_analyze_markdown(capsys):
    main(["analyze", "--events", str(FIXTURE), "--format", "markdown", "--fail-on", "never"])
    out = capsys.readouterr().out
    assert "# Telemetry discovery report" in out


def test_infer_contract_command_outputs_valid_contract(capsys, tmp_path):
    out_path = tmp_path / "c.json"
    code = main(["infer-contract", "--events", str(FIXTURE), "--output", str(out_path)])
    assert code == 0
    contract = json.loads(out_path.read_text())
    assert contract["service"] == "checkout"
    # lint the generated contract through the CLI
    code = main(["lint-contract", "--contract", str(out_path)])
    assert code == 0


def test_validate_with_events_format_auto(capsys, tmp_path):
    contract_path = tmp_path / "c.json"
    main(["infer-contract", "--events", str(FIXTURE), "--output", str(contract_path)])
    capsys.readouterr()
    code = main(["validate", "--contract", str(contract_path), "--events", str(FIXTURE), "--events-format", "auto", "--fail-on", "never"])
    assert code == 0
