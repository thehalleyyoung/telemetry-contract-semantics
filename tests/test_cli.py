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


def test_cli_lint_contract_pass(capsys):
    assert main(["lint-contract", "--contract", CONTRACT]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_describe_model_summarizes_historical_fixture(capsys):
    code = main(
        [
            "describe-model",
            "--events",
            str(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl"),
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert '"notation": "T ⊨ C"' in output
    assert '"event_count": 5' in output
    assert '"metric": 2' in output
    assert "postgres.replication.lag_bytes" in output
