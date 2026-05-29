from pathlib import Path

from telemetry_contracts.cli import main

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = str(ROOT / "examples/contracts/checkout.contract.json")


def test_cli_validate_pass(capsys):
    code = main(["validate", "--contract", CONTRACT, "--events", str(ROOT / "examples/telemetry/passing.jsonl")])
    output = capsys.readouterr().out
    assert code == 0
    assert "OK" in output


def test_cli_validate_fail_json(capsys):
    code = main(["validate", "--contract", CONTRACT, "--events", str(ROOT / "examples/telemetry/failing.jsonl"), "--format", "json"])
    output = capsys.readouterr().out
    assert code == 1
    assert '"ok": false' in output
    assert "telemetry.allowed_values" in output


def test_cli_static_and_scenario_pass(capsys):
    assert main(["static", "--contract", CONTRACT, str(ROOT / "examples/services")]) == 0
    assert main(["scenario", "--contract", CONTRACT, "--events", str(ROOT / "examples/telemetry/passing.jsonl"), "--id", "payment-timeout"]) == 0
    assert capsys.readouterr().out.count("OK") == 2
