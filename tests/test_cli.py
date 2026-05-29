import json
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


def test_cli_monitor_reports_historical_temporal_response(capsys):
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    code = main(
        [
            "monitor",
            "--contract",
            str(case / "contract.json"),
            "--events",
            str(case / "reconstructed_events_sampled_missing_alert.jsonl"),
            "--format",
            "json",
            "--fail-on",
            "never",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert '"bounded-runtime-monitor-v1"' in output
    assert '"telemetry.temporal_response": 1' in output
    assert '"max_pending_responses": 1' in output


def test_cli_semconv_reports_historical_otlp_policy_findings(capsys):
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    code = main(
        [
            "semconv",
            "--contract",
            str(case / "contract.json"),
            "--events",
            str(case / "reconstructed_events.jsonl"),
            "--format",
            "json",
            "--fail-on",
            "never",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert '"semconv.local_policy"' in output
    assert "OpenTelemetry database semantic conventions" in output


def test_cli_event_windows_reports_historical_ownership_units(capsys):
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    code = main(
        [
            "report",
            "event-windows",
            "--contract",
            str(case / "contract.json"),
            "--events",
            str(case / "reconstructed_events_sampled_missing_alert.jsonl"),
            "--dimension",
            "incident",
            "--incident-slice-ms",
            "2000",
            "--format",
            "json",
            "--fail-on",
            "never",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert '"event-window-grouping-v1"' in output
    assert '"id": "incident:slice_ms=2000"' in output
    assert '"telemetry.temporal_response": 1' in output


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


def test_cli_collector_export_analysis_and_roundtrip_export(capsys):
    otlp_path = ROOT / "examples/otlp/collector_coverage_all_signals.otlp.json"
    code = main(["analyze-collector-export", "--input", str(otlp_path), "--format", "markdown"])
    output = capsys.readouterr().out
    assert code == 0
    assert "Collector export analysis" in output
    assert "PII/secret risks: 1" in output
    assert "Unsupported features: 2" in output

    roundtrip_path = ROOT / ".pytest_roundtrip.otlp.json"
    try:
        code = main(["export-otlp", "--events", str(ROOT / "examples/otlp/collector_mixed_signals.events.jsonl"), "--output", str(roundtrip_path)])
        output = capsys.readouterr().out
        assert code == 0
        assert "Wrote OTLP JSON" in output
        assert "resourceSpans" in roundtrip_path.read_text()
    finally:
        roundtrip_path.unlink(missing_ok=True)


def test_cli_collector_pipeline_preservation_fixture(capsys):
    code = main(
        [
            "preservation",
            "--contract",
            str(ROOT / "examples/otlp/collector_pipeline.contract.json"),
            "--before-events",
            str(ROOT / "examples/otlp/collector_pipeline_before.jsonl"),
            "--after-events",
            str(ROOT / "examples/otlp/collector_pipeline_after.jsonl"),
            "--format",
            "json",
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert '"pass": true' in output
    assert "collector-preserves-checkout" in output


def test_cli_doctor_and_common_output_filters(capsys, tmp_path):
    output = tmp_path / "validate_filtered.json"
    code = main([
        "validate",
        "--contract",
        CONTRACT,
        "--events",
        str(ROOT / "examples/telemetry/failing.jsonl"),
        "--format",
        "json",
        "--code",
        "telemetry.allowed_values",
        "--output",
        str(output),
        "--fail-on",
        "never",
    ])
    assert code == 0
    text = output.read_text()
    assert "telemetry.allowed_values" in text
    assert "telemetry.missing_field" not in text
    assert main(["doctor", "--format", "json", "--report-path", str(ROOT / "reports/current_impact.md")]) == 0
    doctor_output = capsys.readouterr().out
    assert '"tool": "telemetry-contracts-doctor-v1"' in doctor_output
    assert "python_version" in doctor_output


def test_cli_init_scaffolds_contract_ci_and_readiness_report(tmp_path):
    out = tmp_path / "starter"
    code = main(["init", "--service", "orders", "--owner", "orders-team", "--output-dir", str(out), "--format", "json"])
    assert code == 0
    assert (out / "contract.json").exists()
    assert (out / "events.jsonl").exists()
    assert (out / "ci-telemetry-contracts.sh").exists()
    assert "orders-team" in (out / "owner_metadata.json").read_text()
    assert "Incident-readiness report" in (out / "incident_readiness.md").read_text()
    assert main(["validate", "--contract", str(out / "contract.json"), "--events", str(out / "events.jsonl")]) == 0


def test_cli_service_owner_report_summarizes_gitlab_fixture(capsys):
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    code = main([
        "report",
        "service-owner",
        "--contract",
        str(case / "contract.json"),
        "--events",
        str(case / "reconstructed_events_sampled_missing_alert.jsonl"),
        "--scenario",
        "restore-readiness",
        "--format",
        "json",
        "--severity",
        "error",
        "--fail-on",
        "never",
    ])
    output = capsys.readouterr().out
    assert code == 0
    assert '"tool": "telemetry-contracts-service-owner-report-v1"' in output
    assert "backup.pg_dump.failed" in output
    report = json.loads(output)
    assert report["findings"]
    assert {finding["severity"] for finding in report["findings"]} == {"error"}
    assert report["summary"]["findings_by_severity"] == {"error": len(report["findings"])}


def test_cli_import_otlp_json_summary(capsys, tmp_path):
    out = tmp_path / "events.jsonl"
    code = main([
        "import-otlp",
        "--input",
        str(ROOT / "examples/otlp/collector_mixed_signals.otlp.json"),
        "--output",
        str(out),
        "--format",
        "json",
    ])
    output = capsys.readouterr().out
    assert code == 0
    assert '"output"' in output
    assert out.exists()
