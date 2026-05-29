from pathlib import Path

from telemetry_contracts.ci_gate import evaluate_ci_gate, format_ci_gate_markdown
from telemetry_contracts.cli import main

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / "examples/ci/static_findings.example.json"
BASELINE = ROOT / "examples/ci/baseline.example.json"


def test_ci_gate_honors_owned_expiring_baseline(capsys):
    report = evaluate_ci_gate(FINDINGS, BASELINE, fail_on="error")
    assert report["summary"]["pass"] is True
    assert report["summary"]["baselined"] == 1
    assert report["summary"]["blocking"] == 0
    assert "Expired baselines: 0" in format_ci_gate_markdown(report)
    assert main(["ci-gate", "--findings", str(FINDINGS), "--baseline", str(BASELINE), "--format", "json"]) == 0
    assert '"pass": true' in capsys.readouterr().out


def test_ci_gate_fails_new_unbaselined_finding(capsys):
    assert main(["ci-gate", "--findings", str(FINDINGS), "--fail-on", "error", "--format", "markdown"]) == 1
    output = capsys.readouterr().out
    assert "Blocking findings" in output
    assert "static.secret_logging" in output
