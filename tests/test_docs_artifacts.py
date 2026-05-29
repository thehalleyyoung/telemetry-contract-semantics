import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_operational_guides_cover_scorecards_privacy_ranges_and_import_limits():
    text = (ROOT / "docs/operational_scorecards.md").read_text(encoding="utf-8")
    for phrase in [
        "HTTP APIs",
        "batch jobs",
        "message consumers",
        "cron tasks",
        "stateful workers",
        "Privacy-safe design examples",
        "Operational ranges to encode",
        "Authoring anti-patterns",
        "CI and review integration",
        "OTLP importer limitations",
        "examples/otlp/collector_coverage_all_signals.otlp.json",
    ]:
        assert phrase in text


def test_report_schema_docs_are_parseable_and_cover_required_reports():
    schema_dir = ROOT / "docs/report_schemas"
    expected = {
        "finding.schema.json",
        "import_diagnostics.schema.json",
        "scenario_report.schema.json",
        "benchmark_report.schema.json",
        "service_owner_report.schema.json",
        "claims_evidence_matrix.schema.json",
    }
    assert {path.name for path in schema_dir.glob("*.schema.json")} == expected
    for path in schema_dir.glob("*.schema.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert data["title"].startswith("Telemetry Contracts")
    docs = (ROOT / "docs/report_schemas.md").read_text(encoding="utf-8")
    for name in expected:
        assert name in docs


def test_replication_and_release_guides_reference_real_artifacts():
    replication = (ROOT / "docs/replication_guide.md").read_text(encoding="utf-8")
    release = (ROOT / "docs/release_checklist.md").read_text(encoding="utf-8")
    for command in [
        "python3 -m pytest -q",
        "make smoke",
        "benchmark --config benchmarks/builtin.json",
        "reports/current_impact.json",
        "case_studies/current/owasp_securetea_signin/Signin.js",
        "reports/paper_tables.md",
    ]:
        assert command in replication
    for phrase in [
        "Mechanized core",
        "Static analysis",
        "Reconstructed data",
        "Benchmark validity",
        "Privacy safeguards",
        "Deterministic non-AI validation",
    ]:
        assert phrase in release
