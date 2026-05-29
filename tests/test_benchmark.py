from pathlib import Path

from telemetry_contracts.benchmark import compare_benchmark_reports, format_diff_markdown, format_markdown, run_benchmark
from telemetry_contracts.cli import main

ROOT = Path(__file__).resolve().parents[1]
BUILTIN = ROOT / "benchmarks/builtin.json"
HISTORICAL_CONTRACT = ROOT / "case_studies/gitlab_2017_database_outage/contract.json"
HISTORICAL_EVENTS = ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl"
DIFF_BASELINE = ROOT / "examples/benchmarks/diff_baseline.report.json"
DIFF_CANDIDATE = ROOT / "examples/benchmarks/diff_candidate.report.json"


def test_builtin_benchmark_reports_labeled_historical_case():
    report = run_benchmark(BUILTIN)
    assert report["summary"]["pass"] is True
    assert report["summary"]["contracts"] == 8
    assert report["summary"]["label_metrics"]["f1"] == 1.0
    assert report["summary"]["findings_per_k_events"] > 0
    assert report["summary"]["top_remediations"]
    assert report["summary"]["events"] > 0
    historical = next(case for case in report["cases"] if case["id"] == "gitlab-2017-database-outage-reconstructed")
    labels = historical["metrics"]["labels"]
    assert historical["metrics"]["validation_pass"] is False
    assert labels["expected"] == 12
    assert labels["matched"] == 12
    assert labels["precision"] == 1.0
    assert labels["recall"] == 1.0
    assert historical["metrics"]["findings_by_code"]["telemetry.missing_field"] == 3
    assert historical["metrics"]["findings_by_code"]["scenario.missing_field"] == 3
    current = next(case for case in report["cases"] if case["id"] == "owasp-securetea-signin-current-static-and-hyperproperty")
    assert current["checks"]["static"] is True
    assert current["checks"]["runtime"] is True
    assert current["metrics"]["labels"]["precision"] == 1.0
    assert current["metrics"]["findings_by_code"]["static.secret_logging"] == 2
    assert current["metrics"]["findings_by_code"]["telemetry.hyper_pii_disclosure"] == 3
    temporal = next(case for case in report["cases"] if case["id"] == "temporal-logic-properties-fail")
    assert temporal["metrics"]["labels"]["expected"] == 5
    assert temporal["metrics"]["labels"]["precision"] == 1.0
    assert temporal["metrics"]["findings_by_code"]["telemetry.temporal_response"] == 1
    otlp = next(case for case in report["cases"] if case["id"] == "otlp-collector-mixed-signals-pass")
    assert otlp["metrics"]["validation_pass"] is True
    assert otlp["metrics"]["findings"] == 0
    coverage = next(case for case in report["cases"] if case["id"] == "otlp-collector-coverage-analysis")
    assert coverage["metrics"]["labels"]["expected"] == 4
    assert coverage["metrics"]["findings_by_code"]["otlp.dropped_evidence"] == 2
    correlation = next(case for case in report["cases"] if case["id"] == "benchmark-missing-correlation")
    assert correlation["metrics"]["labels"]["recall"] == 1.0
    assert correlation["metrics"]["findings_by_code"]["telemetry.correlation_missing"] == 2
    cardinality = next(case for case in report["cases"] if case["id"] == "benchmark-cardinality-budget")
    assert cardinality["metrics"]["findings_by_code"]["telemetry.cardinality"] == 1
    privacy = next(case for case in report["cases"] if case["id"] == "benchmark-privacy-static-source")
    assert privacy["checks"]["static"] is True
    assert privacy["metrics"]["findings_by_code"]["static.unbounded_label"] == 1
    partial = next(case for case in report["cases"] if case["id"] == "benchmark-partial-otlp-diagnostics")
    assert partial["checks"]["import_diagnostics"] is True
    assert partial["metrics"]["import_loss_rate"] == 0.333333


def test_benchmark_markdown_and_cli(capsys):
    report = run_benchmark(BUILTIN)
    markdown = format_markdown(report)
    assert "# Benchmark: built-in telemetry contracts benchmark" in markdown
    assert "gitlab-2017-database-outage-reconstructed" in markdown
    assert main(["benchmark", "--config", str(BUILTIN), "--format", "markdown"]) == 0
    output = capsys.readouterr().out
    assert "Label precision" in output
    assert "Top remediations" in output


def test_benchmark_filters_and_metadata(capsys):
    report = run_benchmark(BUILTIN, filters={"tag": ["privacy"], "check_type": ["static"]})
    assert report["summary"]["cases"] == 1
    case = report["cases"][0]
    assert case["id"] == "benchmark-privacy-static-source"
    assert case["dataset_metadata"]["id"] == "public-benchmark-semantics-fixtures"
    assert "pii non-disclosure" in case["semantics_features"]
    owner_report = run_benchmark(BUILTIN, filters={"service_owner": ["collector-platform"], "disclosure_status": ["public-fixture"]})
    assert [case["id"] for case in owner_report["cases"]] == ["otlp-collector-coverage-analysis", "benchmark-partial-otlp-diagnostics"]
    assert main(["benchmark", "--config", str(BUILTIN), "--case-id", "benchmark-cardinality-budget", "--format", "markdown"]) == 0
    output = capsys.readouterr().out
    assert "benchmark-cardinality-budget" in output
    assert "benchmark-missing-correlation" not in output
    assert main(["benchmark", "--config", str(BUILTIN), "--service-owner", "collector-platform", "--disclosure-status", "public-fixture", "--format", "markdown"]) == 0
    output = capsys.readouterr().out
    assert "benchmark-partial-otlp-diagnostics" in output
    assert "otlp-collector-coverage-analysis" in output
    assert "benchmark-privacy-static-source" not in output


def test_benchmark_diff_report_and_cli(capsys):
    report = compare_benchmark_reports(DIFF_BASELINE, DIFF_CANDIDATE)
    assert report["summary"]["changed_cases"] == 1
    assert report["summary"]["findings_delta"] == 1
    assert report["cases"][0]["findings_by_code_delta"]["otlp.malformed_record"] == 1
    markdown = format_diff_markdown(report)
    assert "Benchmark diff" in markdown
    assert "import loss accounting" in markdown
    assert main(["benchmark-diff", "--baseline", str(DIFF_BASELINE), "--candidate", str(DIFF_CANDIDATE), "--format", "markdown"]) == 0
    output = capsys.readouterr().out
    assert "Findings delta: 1" in output


def test_historical_case_study_smoke(capsys):
    code = main([
        "scenario",
        "--contract",
        str(HISTORICAL_CONTRACT),
        "--events",
        str(HISTORICAL_EVENTS),
        "--id",
        "restore-readiness",
        "--fail-on",
        "never",
    ])
    output = capsys.readouterr().out
    assert code == 0
    assert "scenario.missing_field" in output
