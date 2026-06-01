from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

CLAIMS: list[dict[str, Any]] = [
    {
        "id": "zero-config-existing-data",
        "claim": "The tool runs against telemetry you already have (arbitrary JSON/JSONL logs, a JSON array, native JSONL, or OTLP) with no contract authored first: `analyze` reports privacy/diagnosability findings and `infer-contract` writes a conservative draft contract.",
        "public_artifacts": ["README.md", "telemetry_contracts/adapters.py", "telemetry_contracts/discover.py", "telemetry_contracts/infer.py"],
        "tests": ["tests/test_adapters.py", "tests/test_discover.py", "tests/test_infer.py", "tests/test_cli_byod.py"],
        "fixtures": ["tests/fixtures/byod/app_logs.jsonl"],
        "benchmark_rows": [],
        "limitations": ["Kind inference and alias mapping are heuristic; low-confidence rows skip kind-specific checks and inferred contracts are drafts for review."],
    },
    {
        "id": "benchmark-public-fixtures",
        "claim": "The built-in benchmark ties public/reconstructed fixtures to expected semantic labels and precision/recall/F1 metrics.",
        "public_artifacts": ["README.md", "benchmarks/builtin.json", "reports/current_impact.json", "reports/current_impact.md"],
        "tests": ["tests/test_benchmark.py::test_builtin_benchmark_reports_labeled_historical_case"],
        "fixtures": ["case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl", "case_studies/current/owasp_securetea_signin/Signin.js", "examples/benchmarks/privacy_static.events.jsonl"],
        "benchmark_rows": ["gitlab-2017-database-outage-reconstructed", "owasp-securetea-signin-current-static-and-hyperproperty", "benchmark-privacy-static-source"],
        "limitations": ["Finite checked-in fixtures only; not population-level recall."],
    },
    {
        "id": "ci-regression-gate",
        "claim": "CI can fail on new high-severity findings while allowing audited, owned, expiring baseline entries.",
        "public_artifacts": ["examples/ci/baseline.example.json", "examples/ci/github-actions.yml", "examples/ci/generic-ci.sh"],
        "tests": ["tests/test_ci_gate.py"],
        "fixtures": ["examples/ci/static_findings.example.json"],
        "benchmark_rows": ["benchmark-privacy-static-source"],
        "limitations": ["Baseline entries are exact finding keys; broad suppressions are intentionally unsupported."],
    },
    {
        "id": "sarif-static-runtime",
        "claim": "Static and runtime findings can be exported as SARIF with taxonomy-backed rule metadata for code scanning consumers.",
        "public_artifacts": ["telemetry_contracts/sarif.py", "docs/finding_taxonomy.json", "reports/current_impact.sarif"],
        "tests": ["tests/test_sarif.py", "tests/test_cli.py"],
        "fixtures": ["examples/ci/static_findings.example.json"],
        "benchmark_rows": ["benchmark-privacy-static-source", "benchmark-missing-correlation"],
        "limitations": ["SARIF locations are precise for source-span findings and best-effort for event-index findings."],
    },
    {
        "id": "deterministic-regeneration",
        "claim": "Current impact reports, benchmark Markdown, taxonomy summaries, paper tables, and this matrix are regenerated from checked-in artifacts.",
        "public_artifacts": ["reports/current_impact.json", "reports/current_impact.md", "reports/paper_tables.md", "docs/claims_evidence_matrix.json"],
        "tests": ["tests/test_regenerate.py"],
        "fixtures": ["benchmarks/builtin.json"],
        "benchmark_rows": ["all built-in benchmark rows"],
        "limitations": ["Runtime duration fields vary by machine; labels and finding codes are deterministic."],
    },
]


def claims_evidence_matrix(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    commit = _git_commit(root)
    rows = []
    for item in CLAIMS:
        row = dict(item)
        row["commit"] = commit
        row["evidence_exists"] = {path: (root / path).exists() for path in item["public_artifacts"] + item["fixtures"] if path != "all built-in benchmark rows"}
        rows.append(row)
    return {"schema_version": "1.0", "claims": rows, "summary": {"claims": len(rows), "commit": commit}}


def write_claims_evidence_matrix(path: str | Path, repo_root: str | Path = ".") -> dict[str, Any]:
    report = claims_evidence_matrix(repo_root)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"
