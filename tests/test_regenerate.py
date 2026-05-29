import json
from pathlib import Path

from telemetry_contracts.claims import claims_evidence_matrix
from telemetry_contracts.cli import main
from telemetry_contracts.regenerate import format_regeneration_markdown, regenerate_artifacts

ROOT = Path(__file__).resolve().parents[1]


def test_regeneration_plan_lists_public_artifacts():
    report = regenerate_artifacts(ROOT, write=False)
    assert "reports/current_impact.json" in report["artifacts"]
    assert "reports/current_impact.sarif" in report["artifacts"]
    assert "reports/paper_tables.md" in report["artifacts"]
    assert report["summary"]["cases"] >= 8
    assert "reports/current_impact.json" in format_regeneration_markdown(report)


def test_claims_matrix_maps_claims_to_existing_evidence(capsys):
    matrix = claims_evidence_matrix(ROOT)
    assert matrix["summary"]["claims"] >= 4
    assert all(any(row["evidence_exists"].values()) for row in matrix["claims"])
    assert main(["claims-matrix", "--format", "markdown"]) == 0
    assert "Claims-to-evidence matrix" in capsys.readouterr().out


def test_regenerate_cli_json(capsys):
    assert main(["regenerate-artifacts", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["label_metrics"]["f1"] == 1.0
