from pathlib import Path

from telemetry_contracts.benchmark import format_markdown, run_benchmark
from telemetry_contracts.cli import main

ROOT = Path(__file__).resolve().parents[1]
BUILTIN = ROOT / "benchmarks/builtin.json"
HISTORICAL_CONTRACT = ROOT / "case_studies/gitlab_2017_database_outage/contract.json"
HISTORICAL_EVENTS = ROOT / "case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl"


def test_builtin_benchmark_reports_labeled_historical_case():
    report = run_benchmark(BUILTIN)
    assert report["summary"]["pass"] is True
    assert report["summary"]["contracts"] == 2
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


def test_benchmark_markdown_and_cli(capsys):
    report = run_benchmark(BUILTIN)
    markdown = format_markdown(report)
    assert "# Benchmark: built-in telemetry contracts benchmark" in markdown
    assert "gitlab-2017-database-outage-reconstructed" in markdown
    assert main(["benchmark", "--config", str(BUILTIN), "--format", "markdown"]) == 0
    output = capsys.readouterr().out
    assert "Label precision" in output


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
