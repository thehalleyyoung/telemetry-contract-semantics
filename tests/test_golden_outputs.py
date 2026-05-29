import json
from pathlib import Path

from telemetry_contracts.benchmark import format_markdown, run_benchmark
from telemetry_contracts.cli import main
from telemetry_contracts.otlp import load_otlp_jsonl_detailed

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests/fixtures/golden"


def _read_json(name: str):
    return json.loads((GOLDEN / name).read_text())


def test_benchmark_report_golden_projection():
    report = run_benchmark(ROOT / "benchmarks/builtin.json")
    projection = {
        "summary": {
            "cases": report["summary"]["cases"],
            "contracts": report["summary"]["contracts"],
            "events": report["summary"]["events"],
            "findings_by_code": {k: report["summary"]["findings_by_code"][k] for k in ["telemetry.missing_field", "telemetry.missing_signal", "telemetry.correlation_missing", "otlp.dropped_evidence"]},
            "label_metrics": report["summary"]["label_metrics"],
            "pass": report["summary"]["pass"],
        },
        "case_ids": sorted(case["id"] for case in report["cases"]),
    }
    assert projection == _read_json("benchmark_projection.json")


def test_cli_validate_json_golden_projection(capsys):
    code = main([
        "validate",
        "--contract",
        str(ROOT / "examples/contracts/checkout.contract.json"),
        "--events",
        str(ROOT / "examples/telemetry/failing.jsonl"),
        "--format",
        "json",
    ])
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    projection = {"ok": payload["ok"], "codes": sorted({item["code"] for item in payload["findings"]}), "format": "json"}
    assert projection == _read_json("cli_validate_json_projection.json")


def test_benchmark_markdown_golden_fragments():
    markdown = format_markdown(run_benchmark(ROOT / "benchmarks/builtin.json"))
    for fragment in (GOLDEN / "benchmark_markdown_fragments.txt").read_text().splitlines():
        assert fragment in markdown


def test_sarif_golden_projection(capsys):
    assert main(["sarif", "--findings", str(ROOT / "reports/gitlab_2017_strict_validation.json"), "--tool-name", "telemetry-contracts-golden"]) == 0
    sarif = json.loads(capsys.readouterr().out)
    projection = {
        "version": sarif["version"],
        "tool_name": sarif["runs"][0]["tool"]["driver"]["name"],
        "minimum_results": 1 if sarif["runs"][0]["results"] else 0,
        "rule_ids": sorted({rule["id"] for rule in sarif["runs"][0]["tool"]["driver"]["rules"]}),
    }
    assert projection == _read_json("sarif_projection.json")


def test_importer_diagnostics_golden_projection():
    report = load_otlp_jsonl_detailed(ROOT / "examples/otlp/collector_malformed_records.otlp.jsonl")
    projection = {
        "events": report["summary"]["events"],
        "invalidating_diagnostics": report["summary"]["invalidating_diagnostics"],
        "diagnostics_by_code": report["summary"]["diagnostics_by_code"],
    }
    assert projection == _read_json("importer_diagnostics_projection.json")


def test_service_owner_report_golden_projection(capsys):
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    assert main([
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
        "--fail-on",
        "never",
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    projection = {"service": report["service"], "pass": report["summary"]["pass"], "finding_codes": sorted(report["summary"]["findings_by_code"])}
    assert projection == _read_json("service_owner_projection.json")


def test_incident_readiness_report_golden_projection(capsys):
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    assert main([
        "report",
        "incident-readiness",
        "--contract",
        str(case / "contract.json"),
        "--events",
        str(case / "reconstructed_events.jsonl"),
        "--scenario",
        "restore-readiness",
        "--format",
        "json",
        "--fail-on",
        "never",
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    projection = {
        "score_version": report["adequacy"]["model"]["name"],
        "scenarios": [item["id"] for item in report["unanswered_questions"]],
        "failing_codes": sorted({item["code"] for item in report["findings"]}),
    }
    assert projection == _read_json("incident_readiness_projection.json")
