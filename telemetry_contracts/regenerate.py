from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .benchmark import format_markdown, run_benchmark
from .claims import write_claims_evidence_matrix
from .sarif import report_to_sarif
from .taxonomy import format_taxonomy_markdown, summarize_finding_records, taxonomy_document


def regeneration_commands() -> list[dict[str, str]]:
    return [
        {"artifact": "reports/current_impact.json", "command": "python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format json --output reports/current_impact.json"},
        {"artifact": "reports/current_impact.md", "command": "python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown --output reports/current_impact.md"},
        {"artifact": "reports/current_impact.sarif", "command": "python3 -m telemetry_contracts.cli sarif --findings reports/current_impact.json --output reports/current_impact.sarif"},
        {"artifact": "reports/current_impact_taxonomy.json", "command": "python3 -m telemetry_contracts.cli taxonomy --findings reports/current_impact.json --format json --output reports/current_impact_taxonomy.json"},
        {"artifact": "reports/current_impact_taxonomy.md", "command": "python3 -m telemetry_contracts.cli taxonomy --findings reports/current_impact.json --format markdown --output reports/current_impact_taxonomy.md"},
        {"artifact": "reports/paper_tables.md", "command": "python3 -m telemetry_contracts.cli regenerate-artifacts --write --format markdown"},
        {"artifact": "docs/claims_evidence_matrix.json", "command": "python3 -m telemetry_contracts.cli claims-matrix --output docs/claims_evidence_matrix.json"},
    ]


def regenerate_artifacts(repo_root: str | Path = ".", *, write: bool = False) -> dict[str, Any]:
    root = Path(repo_root)
    report = run_benchmark(root / "benchmarks/builtin.json")
    artifacts = {
        "reports/current_impact.json": json.dumps(report, indent=2, sort_keys=True),
        "reports/current_impact.md": format_markdown(report),
        "reports/current_impact.sarif": json.dumps(report_to_sarif(report), indent=2, sort_keys=True),
    }
    taxonomy_json = taxonomy_document()
    findings = []
    for case in report.get("cases", []):
        case_findings = []
        if isinstance(case, dict):
            case_findings = [item for item in case.get("findings", []) if isinstance(item, dict)]
            findings.extend(case_findings)
    taxonomy_json["observed_findings"] = summarize_finding_records(findings, sources=[{"path": "reports/current_impact.json", "findings": len(findings)}])
    artifacts["reports/current_impact_taxonomy.json"] = json.dumps(taxonomy_json, indent=2, sort_keys=True)
    artifacts["reports/current_impact_taxonomy.md"] = format_taxonomy_markdown(taxonomy_json)
    artifacts["reports/paper_tables.md"] = format_paper_tables(report)
    if write:
        for rel, content in artifacts.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content.rstrip() + "\n", encoding="utf-8")
        write_claims_evidence_matrix(root / "docs/claims_evidence_matrix.json", root)
    return {"commands": regeneration_commands(), "artifacts": sorted(artifacts), "summary": report["summary"]}


def format_regeneration_markdown(report: dict[str, Any]) -> str:
    lines = ["# Deterministic regeneration commands", "", "| Artifact | Command |", "| --- | --- |"]
    for item in report["commands"]:
        lines.append(f"| `{item['artifact']}` | `{item['command']}` |")
    lines.extend(["", f"Benchmark cases: {report['summary']['cases']}", f"Label F1: {report['summary']['label_metrics']['f1']}", ""])
    return "\n".join(lines)


def format_paper_tables(report: dict[str, Any]) -> str:
    lines = ["# Paper tables", "", "Generated from `benchmarks/builtin.json` by deterministic benchmark execution.", "", "## Benchmark label/performance table", "", "| Case | Checks | Findings | Precision | Recall | F1 | Findings/K events |", "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
    for case in report["cases"]:
        labels = case["metrics"].get("labels") or {}
        checks = ",".join(name for name, enabled in case.get("checks", {}).items() if enabled) or "none"
        lines.append(f"| {case['id']} | {checks} | {case['metrics']['findings']} | {labels.get('precision', 'n/a')} | {labels.get('recall', 'n/a')} | {labels.get('f1', 'n/a')} | {case['metrics'].get('findings_per_k_events', 0)} |")
    lines.append("")
    return "\n".join(lines)
