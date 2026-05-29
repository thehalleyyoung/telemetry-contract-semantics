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


def test_cli_validate_strict_reports_unexpected_public_fixture_fields(capsys):
    code = main(
        [
            "validate",
            "--contract",
            str(ROOT / "case_studies/gitlab_2017_database_outage/contract.json"),
            "--events",
            str(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl"),
            "--strict",
            "--format",
            "json",
            "--fail-on",
            "never",
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "telemetry.strict_unexpected_field" in output
    assert "telemetry.strict_undeclared_signal" in output
    assert "telemetry.strict_unmodeled_service" in output
    assert "telemetry.strict_undocumented_transformation" in output


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


def test_cli_equivalence_reports_historical_sampled_difference(capsys):
    code = main(
        [
            "equivalence",
            "--contract",
            str(ROOT / "case_studies/gitlab_2017_database_outage/contract.json"),
            "--left-events",
            str(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl"),
            "--right-events",
            str(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl"),
            "--scenario",
            "restore-readiness",
            "--format",
            "json",
            "--fail-on-difference",
        ]
    )
    output = capsys.readouterr().out

    assert code == 1
    assert '"equivalent": false' in output
    assert "log:backup.pg_dump.failed" in output



def test_cli_preservation_reports_historical_sampling_regression(capsys):
    code = main(
        [
            "preservation",
            "--contract",
            str(ROOT / "case_studies/gitlab_2017_database_outage/contract.json"),
            "--before-events",
            str(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl"),
            "--after-events",
            str(ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl"),
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert code == 1
    assert '"pass": false' in output
    assert "preservation.scenario_signal" in output


def test_cli_explain_finding_with_public_strict_examples(capsys):
    code = main(
        [
            "explain",
            "telemetry.strict_unexpected_field",
            "--examples",
            str(ROOT / "reports/gitlab_2017_strict_validation.json"),
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert '"formal_clause": "STRICT.field-closed-world"' in output
    assert '"observed_examples"' in output
    assert "reports/gitlab_2017_strict_validation.json" in output


def test_cli_explain_unknown_code_fails(capsys):
    code = main(["explain", "telemetry.not_a_real_code"])
    output = capsys.readouterr().out

    assert code == 1
    assert "Unknown finding code" in output


def test_cli_proof_obligations_reports_historical_evidence(capsys):
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    code = main(
        [
            "proof-obligations",
            "--contract",
            str(case / "contract.json"),
            "--events",
            str(case / "reconstructed_events_strict_drift.jsonl"),
            "--strict",
            "--before-events",
            str(case / "reconstructed_events.jsonl"),
            "--after-events",
            str(case / "reconstructed_events_sampled_missing_alert.jsonl"),
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert '"features_cataloged": 27' in output
    assert '"formal_clause": "STRICT.field-closed-world"' in output
    assert '"formal_clause": "PRES.adequacy-signal"' in output


def test_cli_validate_public_hyperproperty_case_study(capsys):
    case = ROOT / "case_studies/current/owasp_securetea_signin"
    code = main(
        [
            "validate",
            "--contract",
            str(case / "contract.json"),
            "--events",
            str(case / "reconstructed_console_events.jsonl"),
            "--format",
            "json",
            "--fail-on",
            "never",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert "telemetry.hyper_pii_disclosure" in output
    assert "signin-console-no-raw-sensitive-values" in output
