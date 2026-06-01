from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .adapters import load_events_auto
from .discover import analyze_events, format_discovery_markdown
from .findings import Finding, has_at_least
from .incident_report import format_incident_readiness_markdown, generate_incident_readiness_report
from .infer import infer_contract
from .loader import ContractLoadError, load_contract, load_jsonl
from .repo_scan import RepoScanError, format_scan_markdown, format_scan_text, scan_directory, scan_repo
from .otlp import analyze_otlp_report, convert_events_to_otlp_payload, format_collector_analysis_markdown, load_otlp_json_detailed, load_otlp_jsonl_detailed, write_diagnostics, write_jsonl
from .scenario import check_scenario, choose_scenario
from .semantics import describe_model, format_model_markdown
from .preservation import check_transformation_preservation, format_preservation_markdown
from .static_checker import check_sources
from .alternatives import evaluate_alternative_obligations, format_alternative_obligations_markdown
from .abstract_domains import format_abstract_domains_markdown, summarize_abstract_domains
from .assume_guarantee import evaluate_assume_guarantee, format_assume_guarantee_markdown
from .benchmark import BenchmarkLoadError, compare_benchmark_reports, format_diff_markdown, format_markdown, run_benchmark
from .core_semantics import evaluate_contract_semantics, format_core_semantics_markdown
from .project_semantics import (
    format_semantics_markdown,
    format_semantics_text,
    infer_execution_semantics,
)
from .pipeline import (
    characterize_repo,
    collect_events,
    diagnose,
    format_characterization_text,
    format_diagnosis_text,
    format_pipeline_text,
    run_pipeline,
)
from .taxonomy import format_taxonomy_markdown, taxonomy_report
from .explain import explain_finding, format_explanation_markdown
from .validator import validate_contract_shape, validate_events
from .equivalence import compare_observational_equivalence, format_equivalence_markdown
from .proof_obligations import format_proof_obligations_markdown, generate_proof_obligations_report
from .refinement import check_contract_refinement, format_refinement_markdown
from .contract_diff import format_contract_diff_markdown, generate_contract_diff_report
from .composition import analyze_contract_composition, format_composition_markdown
from .monitor import format_monitor_markdown, run_compiled_monitor
from .windows import format_event_window_markdown, generate_event_window_report
from .semconv import format_semconv_markdown, lint_semantic_conventions
from .ci_gate import evaluate_ci_gate, format_ci_gate_markdown
from .claims import claims_evidence_matrix, write_claims_evidence_matrix
from .regenerate import format_regeneration_markdown, regenerate_artifacts
from .sarif import findings_to_sarif, pipeline_differential_to_sarif, report_to_sarif
from .doctor import format_doctor_markdown, run_doctor
from .init_workflow import scaffold_project
from .service_report import format_service_owner_markdown, generate_service_owner_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="telemetry-contracts", description="Find observability gaps in the telemetry you already have, then optionally enforce them with contracts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate JSONL telemetry against a contract")
    validate_parser.add_argument("--contract", required=True)
    validate_parser.add_argument("--events", required=True)
    validate_parser.add_argument("--events-format", choices=["native", "auto"], default="native", help="'auto' adapts arbitrary JSON/JSONL/OTLP telemetry you already have")
    validate_parser.add_argument("--strict", action="store_true", help="also reject unmodeled services, undeclared signals, unexpected fields, and undocumented transformations")
    _common_output_args(validate_parser)

    analyze_parser = subparsers.add_parser("analyze", help="zero-config: find privacy and diagnosability issues in telemetry you already have, no contract required")
    analyze_parser.add_argument("--events", required=True, help="JSON/JSONL log lines, a JSON array, native JSONL, or an OTLP export")
    analyze_parser.add_argument("--service", help="only analyze events from this service")
    analyze_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    analyze_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    analyze_parser.add_argument("--output", help="write command output to this path instead of stdout")

    infer_parser = subparsers.add_parser("infer-contract", help="generate a draft contract from telemetry you already have")
    infer_parser.add_argument("--events", required=True, help="JSON/JSONL log lines, a JSON array, native JSONL, or an OTLP export")
    infer_parser.add_argument("--service", help="service name for the inferred contract (defaults to the most common observed service)")
    infer_parser.add_argument("--infer-ranges", action="store_true", help="also infer numeric min/max bounds from observed values (more brittle)")
    infer_parser.add_argument("--output", help="write the inferred contract here instead of stdout")

    scan_parser = subparsers.add_parser("scan", help="discover and analyze telemetry files in a local project directory, no contract required")
    scan_parser.add_argument("--path", default=".", help="project directory to scan for telemetry/log files (default: current directory)")
    scan_parser.add_argument("--service", help="only analyze events from this service")
    scan_parser.add_argument("--max-files", type=int, default=300, help="maximum candidate files to scan")
    scan_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    scan_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    scan_parser.add_argument("--deep", action="store_true", help="also infer per-service execution semantics, observed order, and runtime/source alignment")
    scan_parser.add_argument("--output", help="write command output to this path instead of stdout")

    scan_repo_parser = subparsers.add_parser("scan-repo", help="download a GitHub repository and analyze whatever telemetry it ships, in any format")
    scan_repo_parser.add_argument("--repo", required=True, help="GitHub 'owner/repo' or a full https/git clone URL")
    scan_repo_parser.add_argument("--ref", help="branch or tag to clone (defaults to the repository's default branch)")
    scan_repo_parser.add_argument("--service", help="only analyze events from this service")
    scan_repo_parser.add_argument("--max-files", type=int, default=300, help="maximum candidate files to scan")
    scan_repo_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    scan_repo_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    scan_repo_parser.add_argument("--deep", action="store_true", help="also infer per-service execution semantics, observed order, and runtime/source alignment")
    scan_repo_parser.add_argument("--output", help="write command output to this path instead of stdout")

    mine_parser = subparsers.add_parser("mine-corpus", help="run the observability study over a pinned-commit corpus of pre-existing repositories")
    mine_parser.add_argument("--manifest", required=True, help="path to a corpus manifest (telemetry-contracts/corpus@1)")
    mine_parser.add_argument("--tier", type=int, default=None, help="only mine subjects at or below this tier (smaller = faster subset)")
    mine_parser.add_argument("--service", help="only analyze events from this service")
    mine_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    mine_parser.add_argument("--output", help="write the dataset/report to this path instead of stdout")
    mine_parser.add_argument("--dataset-output", help="also write the full JSON dataset to this path")

    download_parser = subparsers.add_parser("corpus-download", help="clone every corpus subject at its pinned SHA into a (gitignored) local directory for reuse")
    download_parser.add_argument("--manifest", required=True, help="path to a corpus manifest (telemetry-contracts/corpus@1)")
    download_parser.add_argument("--tier", type=int, default=None, help="only download subjects at or below this tier")
    download_parser.add_argument("--repos-dir", default="benchmarks/corpus/_repos", help="directory to clone subjects into (gitignored)")
    download_parser.add_argument("--output", help="write the JSON download report to this path instead of stdout")

    run_parser = subparsers.add_parser("corpus-run", help="run the study incrementally with a content-addressed cache and a resumable, crash-safe status table")
    run_parser.add_argument("--manifest", required=True, help="path to a corpus manifest (telemetry-contracts/corpus@1)")
    run_parser.add_argument("--tier", type=int, default=None, help="only run subjects at or below this tier")
    run_parser.add_argument("--service", help="only analyze events from this service")
    run_parser.add_argument("--cache-dir", default="benchmarks/corpus/.cache", help="content-addressed cache + status directory (gitignored)")
    run_parser.add_argument("--repos-dir", default=None, help="persist checkouts here for reuse (gitignored); omit to use disposable temp clones")
    run_parser.add_argument("--format", choices=["json", "markdown", "correlation", "plots"], default="markdown")
    run_parser.add_argument("--output", help="write the report to this path instead of stdout")
    run_parser.add_argument("--dataset-output", help="also write the full JSON dataset to this path")
    run_parser.add_argument("--plots-dir", help="when --format=plots, write the SVG plots into this directory")

    discover_parser = subparsers.add_parser("corpus-discover", help="PROPOSE candidate repositories from live search (never consumed by the study; pin + verify before use)")
    discover_parser.add_argument("--language", action="append", default=[], help="language to search for (repeatable)")
    discover_parser.add_argument("--min-stars", type=int, default=50, help="minimum star count")
    discover_parser.add_argument("--per-language", type=int, default=20, help="candidates per language")
    discover_parser.add_argument("--include-gitlab", action="store_true", help="also propose popular GitLab projects")
    discover_parser.add_argument("--output", help="write the JSON seed proposal to this path instead of stdout")

    verify_parser = subparsers.add_parser("corpus-verify", help="verify every manifest subject resolves to its pinned commit (network)")
    verify_parser.add_argument("--manifest", required=True, help="path to a corpus manifest (telemetry-contracts/corpus@1)")
    verify_parser.add_argument("--tier", type=int, default=None, help="only verify subjects at or below this tier")
    verify_parser.add_argument("--output", help="write the JSON verification report to this path instead of stdout")

    curate_parser = subparsers.add_parser("corpus-curate", help="clone candidate repos, pin each to its real HEAD SHA, keep only those that ship telemetry, and write a verified manifest")
    curate_parser.add_argument("--candidates", required=True, help="JSON file: a list of targets, or {\"candidates\": [{\"target\": ...}]}")
    curate_parser.add_argument("--work-dir", default="benchmarks/corpus/_curate", help="gitignored directory to clone candidates into")
    curate_parser.add_argument("--output", required=True, help="write the verified corpus manifest to this path")
    curate_parser.add_argument("--tier", type=int, default=2, help="tier to assign to verified subjects")
    curate_parser.add_argument("--limit", type=int, default=None, help="stop after keeping this many subjects")
    curate_parser.add_argument("--allow-no-telemetry", action="store_true", help="also keep verified repos that ship no telemetry (graceful-path samples)")
    curate_parser.add_argument("--description", default="A frozen, pinned-commit corpus of public repositories curated from live code search, each cloned and verified to ship parseable telemetry and pinned to an exact HEAD commit SHA. Authored without this tool in mind.", help="selection-protocol description written into the manifest")

    eval_gold_parser = subparsers.add_parser("evaluate-gold", help="score the detectors against a hand-labeled ground-truth set (precision/recall/F1)")
    eval_gold_parser.add_argument("--gold", required=True, action="append", help="path to a gold JSONL file (telemetry-contracts/gold@1); repeatable")
    eval_gold_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    eval_gold_parser.add_argument("--output", help="write the evaluation dataset/report to this path instead of stdout")
    eval_gold_parser.add_argument("--min-f1", type=int, default=None, help="exit non-zero if the overall micro F1 (per-mille, 0-1000) is below this floor")
    eval_gold_parser.add_argument("--min-class-f1", type=int, default=None, help="exit non-zero if any per-class F1 (per-mille, 0-1000) is below this floor")

    baselines_parser = subparsers.add_parser("compare-baselines", help="score the tool against deterministic comparison baselines on a gold set (head-to-head)")
    baselines_parser.add_argument("--gold", required=True, action="append", help="path to a gold JSONL file (telemetry-contracts/gold@1); repeatable")
    baselines_parser.add_argument("--cache", default="benchmarks/baselines/llm_recorded.json", help="recorded-surrogate response cache (JSON) for the LLM-baseline harness")
    baselines_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    baselines_parser.add_argument("--output", help="write the comparison/report to this path instead of stdout")

    formal_parser = subparsers.add_parser("formal-model", help="discharge the formal guarantees (refinement, monotonicity, termination, assume-guarantee, abstract domains, preservation) as machine-checkable verdicts")
    formal_parser.add_argument("--format", choices=["json", "markdown", "traceability"], default="markdown")
    formal_parser.add_argument("--events", help="optional JSON/JSONL telemetry to drive the data-dependent witnesses")
    formal_parser.add_argument("--output", help="write the report to this path instead of stdout")
    formal_parser.add_argument("--require-all", action="store_true", help="exit non-zero unless every obligation is discharged")

    execp_parser = subparsers.add_parser("execute-proposals", help="produce a safe execution proof: regenerate, AST-validate, and run the tool's own generated instrumentation in a hardened isolated subprocess (never the target repo's code) to prove compile/load/emission")
    execp_parser.add_argument("--path", required=True, help="local repository/directory to analyze")
    execp_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    execp_parser.add_argument("--service", help="restrict the pipeline to a single service")
    execp_parser.add_argument("--timeout", type=int, default=10, help="per-proposal subprocess timeout (seconds)")
    execp_parser.add_argument("--output", help="write the proof to this path instead of stdout")

    infer_semantics_parser = subparsers.add_parser("infer-semantics", help="infer execution semantics (a draft contract + small-step derivation + observed order) from telemetry you already have")
    infer_semantics_parser.add_argument("--events", required=True, help="JSON/JSONL log lines, a JSON array, native JSONL, or an OTLP export")
    infer_semantics_parser.add_argument("--service", help="only reason about events from this service (defaults to the most common observed service)")
    infer_semantics_parser.add_argument("--no-sequences", action="store_true", help="skip inferring the observed execution order")
    infer_semantics_parser.add_argument("--strict", action="store_true", help="also apply closed-world strict obligations during evaluation")
    infer_semantics_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    infer_semantics_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="never")
    infer_semantics_parser.add_argument("--output", help="write command output to this path instead of stdout")

    characterize_parser = subparsers.add_parser("characterize", help="inventory a project's existing telemetry, instrumentation libraries, and archetype, no config required")
    characterize_parser.add_argument("--path", default=".", help="project directory to characterize (default: current directory)")
    characterize_parser.add_argument("--max-files", type=int, default=300, help="maximum candidate files to scan")
    characterize_parser.add_argument("--format", choices=["text", "json"], default="text")
    characterize_parser.add_argument("--output", help="write command output to this path instead of stdout")

    diagnose_parser = subparsers.add_parser("diagnose", help="score how diagnosable existing telemetry is, list unanswerable incident questions, and rank fixes by leverage")
    diagnose_parser.add_argument("--events", help="a telemetry file in any supported format")
    diagnose_parser.add_argument("--path", help="a project directory; diagnose all discovered telemetry")
    diagnose_parser.add_argument("--service", help="only diagnose events from this service")
    diagnose_parser.add_argument("--format", choices=["text", "json"], default="text")
    diagnose_parser.add_argument("--fail-under", type=int, help="exit non-zero if the diagnosability score is below this value")
    diagnose_parser.add_argument("--output", help="write command output to this path instead of stdout")

    pipeline_parser = subparsers.add_parser("pipeline", help="run the staged improvement loop on a project: characterize -> diagnose -> plan -> apply (offline) -> differential, in rounds")
    pipeline_parser.add_argument("--path", default=".", help="project directory to improve (default: current directory)")
    pipeline_parser.add_argument("--repo", help="instead of --path, clone this GitHub 'owner/repo' or URL and run the pipeline on it")
    pipeline_parser.add_argument("--ref", help="branch or tag to clone when --repo is used")
    pipeline_parser.add_argument("--service", help="only run the loop on this service")
    pipeline_parser.add_argument("--rounds", type=int, default=3, help="maximum improvement rounds (default: 3)")
    pipeline_parser.add_argument("--max-changes", type=int, default=5, help="maximum instrumentation changes proposed per round")
    pipeline_parser.add_argument("--out-dir", help="persist every stage as SHA-keyed, content-addressable JSON artifacts under this directory")
    pipeline_parser.add_argument("--cache-dir", help="with --repo, cache the clone under a content-addressed key here so re-runs on the same ref skip re-downloading")
    pipeline_parser.add_argument("--fail-on-regression", action="store_true", help="exit non-zero if any round regressed safety/diagnosability")
    pipeline_parser.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    pipeline_parser.add_argument("--output", help="write command output to this path instead of stdout")

    lint_parser = subparsers.add_parser("lint-contract", help="lint contract shape and schema semantics without telemetry events")
    lint_parser.add_argument("--contract", required=True)
    _common_output_args(lint_parser)

    static_parser = subparsers.add_parser("static", help="check source files for expected instrumentation names")
    static_parser.add_argument("--contract", required=True)
    static_parser.add_argument("sources", nargs="+")
    _common_output_args(static_parser)

    scenario_parser = subparsers.add_parser("scenario", help="check diagnosability requirements for a scenario")
    scenario_parser.add_argument("--contract", required=True)
    scenario_parser.add_argument("--events", required=True)
    scenario_parser.add_argument("--id")
    scenario_parser.add_argument("--question")
    _common_output_args(scenario_parser)

    otlp_parser = subparsers.add_parser("import-otlp", help="convert OTLP JSON or JSONL exports to telemetry-contracts JSONL")
    otlp_parser.add_argument("--input", required=True)
    otlp_parser.add_argument("--output", required=True)
    otlp_parser.add_argument("--input-format", choices=["json", "jsonl"], default="json")
    otlp_parser.add_argument("--diagnostics-output", help="optional JSON file with normalization/skipped-record diagnostics")
    otlp_parser.add_argument("--format", choices=["text", "json"], default="text")

    export_otlp_parser = subparsers.add_parser("export-otlp", help="convert telemetry-contracts JSONL back to collector-style OTLP JSON for importer differential tests")
    export_otlp_parser.add_argument("--events", required=True)
    export_otlp_parser.add_argument("--output", required=True)

    collector_parser = subparsers.add_parser("analyze-collector-export", help="summarize OTLP collector export loss, schema, cardinality, PII, temporality, and unsupported-feature risks")
    collector_parser.add_argument("--input", required=True)
    collector_parser.add_argument("--input-format", choices=["json", "jsonl"], default="json")
    collector_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    collector_parser.add_argument("--output")
    collector_parser.add_argument("--cardinality-threshold", type=int, default=2)

    model_parser = subparsers.add_parser("describe-model", help="describe the observation domain and satisfaction relation")
    model_parser.add_argument("--events", help="optional JSONL artifact to summarize against the observation model")
    model_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    model_parser.add_argument("--output")

    abstract_parser = subparsers.add_parser("abstract-domains", help="summarize finite abstract domains for contract/event reasoning")
    abstract_parser.add_argument("--contract", required=True)
    abstract_parser.add_argument("--events", help="optional JSONL telemetry evidence")
    abstract_parser.add_argument("--string-bound", type=int, default=5)
    abstract_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    abstract_parser.add_argument("--output")

    semantics_parser = subparsers.add_parser("evaluate-semantics", help="emit the executable small-step contract-evaluation derivation")
    semantics_parser.add_argument("--contract", required=True)
    semantics_parser.add_argument("--events", required=True)
    semantics_parser.add_argument("--strict", action="store_true", help="include strict closed-world semantic side conditions")
    semantics_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    semantics_parser.add_argument("--output")
    semantics_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    monitor_parser = subparsers.add_parser("monitor", help="run compiled bounded-memory runtime monitors over JSONL telemetry")
    monitor_parser.add_argument("--contract", required=True)
    monitor_parser.add_argument("--events", required=True)
    monitor_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    monitor_parser.add_argument("--output")
    monitor_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    benchmark_parser = subparsers.add_parser("benchmark", help="run a benchmark suite from a JSON config")
    benchmark_parser.add_argument("--config", default="benchmarks/builtin.json")
    benchmark_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    benchmark_parser.add_argument("--output")
    benchmark_parser.add_argument("--case-id", action="append", help="only run a benchmark case id; repeatable")
    benchmark_parser.add_argument("--tag", action="append", help="only run cases carrying this tag; repeatable")
    benchmark_parser.add_argument("--check-type", action="append", choices=["runtime", "static", "scenario", "strict", "import_diagnostics"], help="only run cases exercising this check type; repeatable")
    benchmark_parser.add_argument("--dataset", action="append", help="only run cases for this dataset id; repeatable")
    benchmark_parser.add_argument("--expected-failure-mode", action="append", help="only run cases labeled with this expected failure mode; repeatable")
    benchmark_parser.add_argument("--semantics-feature", action="append", help="only run cases labeled with this semantic feature; repeatable")
    benchmark_parser.add_argument("--service-owner", action="append", help="only run cases for this service owner; repeatable")
    benchmark_parser.add_argument("--disclosure-status", action="append", help="only run cases with this disclosure status; repeatable")

    benchmark_diff_parser = subparsers.add_parser("benchmark-diff", help="diff two JSON benchmark reports")
    benchmark_diff_parser.add_argument("--baseline", required=True)
    benchmark_diff_parser.add_argument("--candidate", required=True)
    benchmark_diff_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    benchmark_diff_parser.add_argument("--output")

    semconv_parser = subparsers.add_parser("semconv", help="lint telemetry against OpenTelemetry semantic conventions and local policy")
    semconv_parser.add_argument("--contract", required=True)
    semconv_parser.add_argument("--events", help="optional JSONL telemetry to check in addition to the contract")
    semconv_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    semconv_parser.add_argument("--output")
    semconv_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    taxonomy_parser = subparsers.add_parser("taxonomy", help="emit the machine-readable finding taxonomy and optional observed finding coverage")
    taxonomy_parser.add_argument("--findings", action="append", default=[], help="JSON report containing findings or benchmark cases with findings")
    taxonomy_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    taxonomy_parser.add_argument("--output")

    sarif_parser = subparsers.add_parser("sarif", help="convert a JSON findings or benchmark report to SARIF")
    sarif_parser.add_argument("--findings", required=True, help="JSON report containing findings or benchmark cases with findings")
    sarif_parser.add_argument("--tool-name", default="telemetry-contracts")
    sarif_parser.add_argument("--output")

    ci_gate_parser = subparsers.add_parser("ci-gate", help="fail CI on new findings while honoring owned expiring baselines")
    ci_gate_parser.add_argument("--findings", required=True)
    ci_gate_parser.add_argument("--baseline")
    ci_gate_parser.add_argument("--fail-on", choices=["error", "warning"], default="error")
    ci_gate_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    ci_gate_parser.add_argument("--output")

    ci_report_parser = subparsers.add_parser("ci-report", help="one-shot CI observability report (score, top gaps, unanswered questions) with a configurable score-floor + severity gate and an optional base-branch diff; ideal for the GitHub Action")
    ci_report_parser.add_argument("--path", required=True, help="repository/directory to analyze")
    ci_report_parser.add_argument("--service", help="restrict to a single service")
    ci_report_parser.add_argument("--format", choices=["json", "markdown"], default="markdown", help="json (machine report) or markdown (PR comment)")
    ci_report_parser.add_argument("--base", help="a prior ci-report JSON (e.g. from the PR base branch) to diff the score against")
    ci_report_parser.add_argument("--min-score", type=int, help="fail unless the diagnosability score is at least this value")
    ci_report_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error", help="fail on findings at or above this severity")
    ci_report_parser.add_argument("--max-files", type=int, default=300)
    ci_report_parser.add_argument("--output")

    badge_parser = subparsers.add_parser("scorecard-badge", help="emit a deterministic observability badge/scorecard SVG or a shields.io JSON endpoint from a scan")
    badge_group = badge_parser.add_mutually_exclusive_group(required=True)
    badge_group.add_argument("--path", help="repository/directory to analyze")
    badge_group.add_argument("--report", help="a prior ci-report JSON to render from")
    badge_parser.add_argument("--format", choices=["svg", "scorecard", "shields-json"], default="svg")
    badge_parser.add_argument("--label", default="observability")
    badge_parser.add_argument("--service", help="restrict to a single service")
    badge_parser.add_argument("--max-files", type=int, default=300)
    badge_parser.add_argument("--output")

    regenerate_parser = subparsers.add_parser("regenerate-artifacts", help="list or write deterministic report regeneration artifacts")
    regenerate_parser.add_argument("--write", action="store_true", help="write reports/current_impact*, reports/paper_tables.md, and docs/claims_evidence_matrix.json")
    regenerate_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    regenerate_parser.add_argument("--output")

    claims_parser = subparsers.add_parser("claims-matrix", help="emit README/report claim-to-evidence mapping")
    claims_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    claims_parser.add_argument("--output")

    reproduce_parser = subparsers.add_parser("reproduce", help="regenerate every offline artifact deterministically and verify a SHA-256 manifest")
    reproduce_group = reproduce_parser.add_mutually_exclusive_group()
    reproduce_group.add_argument("--write", action="store_true", help="regenerate all artifacts in place and write reports/reproduce_manifest.json (default)")
    reproduce_group.add_argument("--check", action="store_true", help="regenerate and verify every artifact matches the committed manifest; exit 1 on any drift")
    reproduce_parser.add_argument("--output", help="write the manifest/check report to this path instead of stdout")

    explain_parser = subparsers.add_parser("explain", help="explain a finding code with formal meaning, impact, examples, and fixes")
    explain_parser.add_argument("code", help="finding code such as telemetry.missing_field")
    explain_parser.add_argument("--examples", action="append", default=[], help="JSON finding report to mine for concrete observed examples")
    explain_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    explain_parser.add_argument("--output")

    init_parser = subparsers.add_parser("init", help="scaffold a starter service contract, events, CI gate, owner metadata, and readiness report")
    init_parser.add_argument("--service", required=True)
    init_parser.add_argument("--owner", required=True)
    init_parser.add_argument("--output-dir", default="telemetry-contracts-starter")
    init_parser.add_argument("--force", action="store_true")
    init_parser.add_argument("--format", choices=["json", "text"], default="text")
    init_parser.add_argument("--output")

    doctor_parser = subparsers.add_parser("doctor", help="check local telemetry-contracts runtime, optional YAML, install, collector, report, and CI assumptions")
    doctor_parser.add_argument("--collector-export", action="append", default=[])
    doctor_parser.add_argument("--report-path", action="append", default=[])
    doctor_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    doctor_parser.add_argument("--output")

    equivalence_parser = subparsers.add_parser("equivalence", help="compare two telemetry files by incident-question answerability")
    equivalence_parser.add_argument("--contract", required=True)
    equivalence_parser.add_argument("--left-events", required=True)
    equivalence_parser.add_argument("--right-events", required=True)
    equivalence_parser.add_argument("--scenario", action="append", default=[])
    equivalence_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    equivalence_parser.add_argument("--output")
    equivalence_parser.add_argument("--fail-on-difference", action="store_true")

    preservation_parser = subparsers.add_parser("preservation", help="check whether approved transformations preserve contract and scenario obligations")
    preservation_parser.add_argument("--contract", required=True)
    preservation_parser.add_argument("--before-events", required=True)
    preservation_parser.add_argument("--after-events", required=True)
    preservation_parser.add_argument("--transformation", action="append", default=[])
    preservation_parser.add_argument("--scenario", action="append", default=[])
    preservation_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    preservation_parser.add_argument("--output")
    preservation_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    refinement_parser = subparsers.add_parser("refinement", help="check whether a candidate contract refines a base contract without weakening guarantees")
    refinement_parser.add_argument("--base-contract", required=True)
    refinement_parser.add_argument("--candidate-contract", required=True)
    refinement_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    refinement_parser.add_argument("--output")
    refinement_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    diff_parser = subparsers.add_parser("contract-diff", help="generate a pull-request contract-diff report between two contract versions")
    diff_parser.add_argument("--base-contract", required=True)
    diff_parser.add_argument("--candidate-contract", required=True)
    diff_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    diff_parser.add_argument("--output")
    diff_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="never")

    composition_parser = subparsers.add_parser("compose-contract", help="resolve inherited contract policies and verify parent refinement")
    composition_parser.add_argument("--contract", required=True)
    composition_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    composition_parser.add_argument("--output")
    composition_parser.add_argument("--resolved-output", help="optional path for the fully composed contract JSON")
    composition_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    obligations_parser = subparsers.add_parser("proof-obligations", help="instantiate formal proof-obligation templates for a contract and evidence artifacts")
    obligations_parser.add_argument("--contract", required=True)
    obligations_parser.add_argument("--events", help="optional JSONL runtime trace evidence")
    obligations_parser.add_argument("--strict", action="store_true", help="include strict closed-world satisfaction obligations")
    obligations_parser.add_argument("--before-events", help="optional source JSONL trace for preservation evidence")
    obligations_parser.add_argument("--after-events", help="optional transformed JSONL trace for preservation evidence")
    obligations_parser.add_argument("--benchmark-config", help="optional benchmark config for label-validity evidence")
    obligations_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    obligations_parser.add_argument("--output")
    obligations_parser.add_argument("--fail-on-violated", action="store_true")

    report_parser = subparsers.add_parser("report", help="generate operational reports from contracts and telemetry")
    report_subparsers = report_parser.add_subparsers(dest="report_command", required=True)
    readiness_parser = report_subparsers.add_parser("incident-readiness", help="score incident diagnosability and remediation readiness")
    readiness_parser.add_argument("--contract", required=True)
    readiness_parser.add_argument("--events", required=True)
    readiness_parser.add_argument("--scenario", action="append", default=[])
    readiness_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    readiness_parser.add_argument("--output")
    readiness_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    _report_filter_args(readiness_parser)

    alternative_parser = report_subparsers.add_parser("alternative-obligations", help="explain disjunctive evidence obligations and witnesses")
    alternative_parser.add_argument("--contract", required=True)
    alternative_parser.add_argument("--events", required=True)
    alternative_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    alternative_parser.add_argument("--output")
    alternative_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    _report_filter_args(alternative_parser)

    ag_parser = report_subparsers.add_parser("assume-guarantee", help="partition telemetry obligations by service, collector, environment, and on-call layers")
    ag_parser.add_argument("--contract", required=True)
    ag_parser.add_argument("--events", required=True)
    ag_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    ag_parser.add_argument("--output")
    ag_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    _report_filter_args(ag_parser)

    windows_parser = report_subparsers.add_parser("event-windows", help="group events and findings by trace, request, tenant, deployment, scenario, and incident slices")
    windows_parser.add_argument("--contract", required=True)
    windows_parser.add_argument("--events", required=True)
    windows_parser.add_argument("--dimension", action="append", default=[], help="window dimension: trace, request, tenant, deployment, scenario, incident, or all")
    windows_parser.add_argument("--incident-slice-ms", type=int, help="also group events into bounded incident time slices")
    windows_parser.add_argument("--strict", action="store_true", help="include strict closed-world validation findings before grouping")
    windows_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    windows_parser.add_argument("--output")
    windows_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    _report_filter_args(windows_parser)

    service_owner_parser = report_subparsers.add_parser("service-owner", help="summarize owner coverage, failing obligations, privacy risks, collector/export issues, and remediation priority")
    service_owner_parser.add_argument("--contract", required=True)
    service_owner_parser.add_argument("--events", required=True)
    service_owner_parser.add_argument("--source", action="append", default=[])
    service_owner_parser.add_argument("--scenario", action="append", default=[])
    service_owner_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    service_owner_parser.add_argument("--output")
    service_owner_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    _report_filter_args(service_owner_parser)

    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            loaded = load_events_auto(args.events)
            report = analyze_events(loaded["events"], service=args.service)
            report["input"] = {"format": loaded.get("format"), "summary": loaded.get("summary"), "diagnostics": loaded.get("diagnostics", [])}
            if args.format == "json":
                output = json.dumps(report, indent=2, sort_keys=True)
            elif args.format == "markdown":
                output = format_discovery_markdown(report) + "\n" + _format_discovery_markdown_footer(report, args.events)
            else:
                output = _format_discovery_text(report, args.events)
            _emit_text(output, args.output)
            if args.fail_on == "never":
                return 0
            threshold = {"error": ["error"], "warning": ["error", "warning"]}[args.fail_on]
            return 1 if any(item["severity"] in threshold for item in report["findings"]) else 0
        if args.command == "infer-contract":
            loaded = load_events_auto(args.events)
            contract = infer_contract(loaded["events"], service=args.service, infer_ranges=args.infer_ranges)
            output = json.dumps(contract, indent=2, sort_keys=True)
            _emit_text(output, args.output)
            return 0
        if args.command == "infer-semantics":
            loaded = load_events_auto(args.events)
            report = infer_execution_semantics(
                loaded["events"],
                service=args.service,
                infer_sequences=not args.no_sequences,
                strict=args.strict,
            )
            if args.format == "json":
                output = json.dumps(report, indent=2, sort_keys=True)
            elif args.format == "markdown":
                output = format_semantics_markdown(report)
            else:
                output = format_semantics_text(report)
            _emit_text(output, args.output)
            if args.fail_on == "never":
                return 0
            threshold = {"error": ["error"], "warning": ["error", "warning"]}[args.fail_on]
            return 1 if any(item["severity"] in threshold for item in report["findings"]) else 0
        if args.command == "characterize":
            report = characterize_repo(args.path, max_files=args.max_files)
            if args.format == "json":
                output = json.dumps(report, indent=2, sort_keys=True)
            else:
                output = format_characterization_text(report)
            _emit_text(output, args.output)
            return 0
        if args.command == "diagnose":
            if not args.events and not args.path:
                print("ERROR diagnose: provide --events <file> or --path <dir>", file=sys.stderr)
                return 2
            if args.events:
                events = load_events_auto(args.events)["events"]
            else:
                events = collect_events(args.path)["events"]
            report = diagnose(events, service=args.service)
            if args.format == "json":
                output = json.dumps(report, indent=2, sort_keys=True)
            else:
                output = format_diagnosis_text(report)
            _emit_text(output, args.output)
            if args.fail_under is not None and report["diagnosability_score"] < args.fail_under:
                return 1
            return 0
        if args.command == "pipeline":
            if args.repo:
                try:
                    clone = scan_repo(args.repo, ref=args.ref, service=args.service, max_files=1, deep=False)
                except RepoScanError as exc:
                    print(f"ERROR pipeline: {exc}", file=sys.stderr)
                    return 2
                import tempfile

                from .artifacts import clone_cache_key
                from .repo_scan import clone_repo

                if args.cache_dir:
                    # Content-addressed clone cache: reuse an existing checkout
                    # for the same (repo, ref) so re-runs skip re-downloading.
                    dest = os.path.join(args.cache_dir, clone_cache_key(args.repo, args.ref))
                    tmp = None
                    if not os.path.isdir(os.path.join(dest, ".git")):
                        os.makedirs(args.cache_dir, exist_ok=True)
                        shutil.rmtree(dest, ignore_errors=True)
                        clone_repo(args.repo, dest, ref=args.ref)
                else:
                    # scan_repo clones to a temp dir that is removed on return, so
                    # re-clone into a persistent temp dir we control for the loop.
                    tmp = tempfile.mkdtemp(prefix="telemetry-contracts-pipeline-")
                    dest = os.path.join(tmp, "repo")
                    clone_repo(args.repo, dest, ref=args.ref)
                try:
                    report = run_pipeline(
                        dest,
                        rounds=args.rounds,
                        max_changes_per_round=args.max_changes,
                        service=args.service,
                        out_dir=args.out_dir,
                    )
                    report["characterization"]["manifest"]["root"] = args.repo
                finally:
                    if tmp is not None:
                        shutil.rmtree(tmp, ignore_errors=True)
            else:
                report = run_pipeline(
                    args.path,
                    rounds=args.rounds,
                    max_changes_per_round=args.max_changes,
                    service=args.service,
                    out_dir=args.out_dir,
                )
            if args.format == "json":
                output = json.dumps(report, indent=2, sort_keys=True)
            elif args.format == "sarif":
                output = json.dumps(pipeline_differential_to_sarif(report), indent=2, sort_keys=True)
            else:
                output = format_pipeline_text(report)
            _emit_text(output, args.output)
            if args.fail_on_regression and report.get("regressed"):
                return 1
            return 0
        if args.command == "mine-corpus":
            from .mining import (
                CorpusManifestError,
                load_corpus_manifest,
                mine_corpus,
                render_study_markdown,
            )

            try:
                _protocol, subjects = load_corpus_manifest(args.manifest)
            except CorpusManifestError as exc:
                print(f"ERROR corpus-manifest: {exc}", file=sys.stderr)
                return 2
            if args.tier is not None:
                subjects = [s for s in subjects if s.tier <= args.tier]
            if not subjects:
                print("ERROR corpus-manifest: no subjects selected", file=sys.stderr)
                return 2
            try:
                dataset = mine_corpus(subjects, service=args.service)
            except RepoScanError as exc:
                print(f"ERROR mine-corpus: {exc}", file=sys.stderr)
                return 2
            if args.dataset_output:
                Path(args.dataset_output).write_text(
                    json.dumps(dataset, indent=2, sort_keys=True), encoding="utf-8"
                )
            output = (
                json.dumps(dataset, indent=2, sort_keys=True)
                if args.format == "json"
                else render_study_markdown(dataset)
            )
            _emit_text(output, args.output)
            return 0
        if args.command in {"corpus-download", "corpus-run", "corpus-verify"}:
            from .mining import (
                CorpusManifestError,
                correlate,
                download_corpus,
                load_corpus_manifest,
                render_correlation_markdown,
                render_plots,
                render_study_markdown,
                run_corpus,
            )
            from .mining.runner import verify_corpus

            try:
                _protocol, subjects = load_corpus_manifest(args.manifest)
            except CorpusManifestError as exc:
                print(f"ERROR corpus-manifest: {exc}", file=sys.stderr)
                return 2
            if args.tier is not None:
                subjects = [s for s in subjects if s.tier <= args.tier]
            if not subjects:
                print("ERROR corpus-manifest: no subjects selected", file=sys.stderr)
                return 2

            try:
                if args.command == "corpus-download":
                    report = download_corpus(subjects, args.repos_dir)
                    _emit_text(json.dumps(report, indent=2, sort_keys=True), args.output)
                    return 0 if not report["errors"] else 1
                if args.command == "corpus-verify":
                    report = verify_corpus(subjects)
                    _emit_text(json.dumps(report, indent=2, sort_keys=True), args.output)
                    return 0 if not report["errors"] else 1
                # corpus-run
                dataset = run_corpus(
                    subjects, cache_dir=args.cache_dir,
                    repos_dir=args.repos_dir, service=args.service,
                )
            except RepoScanError as exc:
                print(f"ERROR {args.command}: {exc}", file=sys.stderr)
                return 2

            if args.dataset_output:
                Path(args.dataset_output).write_text(
                    json.dumps(dataset, indent=2, sort_keys=True), encoding="utf-8"
                )
            if args.format == "json":
                output = json.dumps(dataset, indent=2, sort_keys=True)
            elif args.format == "correlation":
                output = render_correlation_markdown(correlate(dataset))
            elif args.format == "plots":
                plots = render_plots(dataset)
                if args.plots_dir:
                    plots_dir = Path(args.plots_dir)
                    plots_dir.mkdir(parents=True, exist_ok=True)
                    for name, svg in sorted(plots.items()):
                        (plots_dir / name).write_text(svg, encoding="utf-8")
                    output = json.dumps(
                        {"plots_dir": str(plots_dir), "files": sorted(plots)},
                        indent=2, sort_keys=True,
                    )
                else:
                    output = json.dumps(
                        {name: svg for name, svg in sorted(plots.items())},
                        indent=2, sort_keys=True,
                    )
            else:
                output = render_study_markdown(dataset)
            _emit_text(output, args.output)
            return 0
        if args.command == "corpus-discover":
            from .mining.discover import discover_candidates

            languages = args.language or ["Python", "JavaScript", "Go"]
            token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
            try:
                seed = discover_candidates(
                    languages=languages, min_stars=args.min_stars,
                    per_language=args.per_language,
                    include_gitlab=args.include_gitlab, token=token,
                )
            except Exception as exc:  # noqa: BLE001 - live network surface
                print(f"ERROR corpus-discover: {exc}", file=sys.stderr)
                return 2
            _emit_text(json.dumps(seed, indent=2, sort_keys=True), args.output)
            return 0

        if args.command == "corpus-curate":
            from .mining.curate import build_manifest, curate_corpus

            try:
                raw = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                print(f"ERROR corpus-curate: cannot read candidates: {exc}", file=sys.stderr)
                return 2
            if isinstance(raw, dict):
                candidates = raw.get("candidates", [])
            else:
                candidates = raw
            kept_count = [0]

            def _on_candidate(target: str, subject: dict | None) -> None:
                status = "kept" if subject is not None else "skip"
                if subject is not None:
                    kept_count[0] += 1
                print(f"  {status:4s} {target}", file=sys.stderr)

            try:
                kept = curate_corpus(
                    candidates, work_dir=args.work_dir,
                    require_telemetry=not args.allow_no_telemetry,
                    tier=args.tier, limit=args.limit, on_candidate=_on_candidate,
                )
            except Exception as exc:  # noqa: BLE001 - live network surface
                print(f"ERROR corpus-curate: {exc}", file=sys.stderr)
                return 2
            manifest = build_manifest(
                kept, description=args.description,
                tier_note=f"Curated tier-{args.tier} subjects, each cloned and verified to ship telemetry.",
            )
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
            )
            print(
                f"corpus-curate: kept {len(manifest['subjects'])} verified subjects -> {args.output}",
                file=sys.stderr,
            )
            return 0

            from .evaluation import (
                GroundTruthError,
                load_gold_set,
                render_evaluation_markdown,
                score_gold_set,
            )

            try:
                items = load_gold_set(*args.gold)
            except GroundTruthError as exc:
                print(f"ERROR gold-set: {exc}", file=sys.stderr)
                return 2
            dataset = score_gold_set(items)
            output = (
                json.dumps(dataset, indent=2, sort_keys=True)
                if args.format == "json"
                else render_evaluation_markdown(dataset)
            )
            _emit_text(output, args.output)
            failed = False
            if args.min_f1 is not None:
                overall_f1 = dataset["overall"]["f1_permille"]
                if overall_f1 is None or overall_f1 < args.min_f1:
                    print(
                        f"ERROR evaluate-gold: overall F1 {overall_f1} below floor {args.min_f1}",
                        file=sys.stderr,
                    )
                    failed = True
            if args.min_class_f1 is not None:
                for gap in sorted(dataset["per_class"]):
                    f1 = dataset["per_class"][gap]["f1_permille"]
                    if f1 is None or f1 < args.min_class_f1:
                        print(
                            f"ERROR evaluate-gold: {gap} F1 {f1} below floor {args.min_class_f1}",
                            file=sys.stderr,
                        )
                        failed = True
            return 1 if failed else 0
        if args.command == "compare-baselines":
            from .evaluation import (
                GroundTruthError,
                compare_baselines,
                load_gold_set,
                render_baselines_markdown,
            )

            try:
                items = load_gold_set(*args.gold)
            except GroundTruthError as exc:
                print(f"ERROR gold-set: {exc}", file=sys.stderr)
                return 2
            try:
                with open(args.cache, encoding="utf-8") as handle:
                    cache = json.load(handle)
            except (OSError, ValueError) as exc:
                print(f"ERROR compare-baselines: cannot read cache {args.cache}: {exc}", file=sys.stderr)
                return 2
            try:
                comparison = compare_baselines(items, cache)
            except KeyError as exc:
                print(f"ERROR compare-baselines: {exc}", file=sys.stderr)
                return 2
            output = (
                json.dumps(comparison, indent=2, sort_keys=True)
                if args.format == "json"
                else render_baselines_markdown(comparison)
            )
            _emit_text(output, args.output)
            return 0
        if args.command == "formal-model":
            from .formal_model import (
                discharge_formal_model,
                render_formal_model_markdown,
                render_traceability_markdown,
            )

            events = None
            if args.events:
                events = load_events_auto(args.events, tolerant=True)["events"]
            report = discharge_formal_model(events=events)
            if args.format == "json":
                output = json.dumps(report, indent=2, sort_keys=True)
            elif args.format == "traceability":
                output = render_traceability_markdown(report)
            else:
                output = render_formal_model_markdown(report)
            _emit_text(output, args.output)
            if args.require_all and not report["summary"]["all_discharged"]:
                print(
                    f"ERROR formal-model: {report['summary']['failed']} obligation(s) not discharged",
                    file=sys.stderr,
                )
                return 1
            return 0
        if args.command == "execute-proposals":
            from .execution import render_execution_proof_markdown

            report = run_pipeline(args.path, service=args.service, prove_execution=True)
            proof = report.get("execution_proof") or {
                "schema": "telemetry-contracts/execution-proof@1",
                "proofs": [],
                "summary": {"proposals": 0, "status_counts": {}, "all_logging_emit_clean": True},
                "honesty": "no proposals were generated (no telemetry gaps to instrument)",
            }
            if args.format == "json":
                output = json.dumps(proof, indent=2, sort_keys=True)
            else:
                output = render_execution_proof_markdown(proof)
            _emit_text(output, args.output)
            return 0
        if args.command in {"scan", "scan-repo"}:
            try:
                if args.command == "scan":
                    report = scan_directory(args.path, service=args.service, max_files=args.max_files, deep=args.deep)
                else:
                    report = scan_repo(args.repo, ref=args.ref, service=args.service, max_files=args.max_files, deep=args.deep)
            except RepoScanError as exc:
                print(f"ERROR repo-scan: {exc}", file=sys.stderr)
                return 2
            if args.format == "json":
                output = json.dumps(report, indent=2, sort_keys=True)
            elif args.format == "markdown":
                output = format_scan_markdown(report)
            else:
                output = format_scan_text(report)
            _emit_text(output, args.output)
            if args.fail_on == "never":
                return 0
            threshold = {"error": ["error"], "warning": ["error", "warning"]}[args.fail_on]
            return 1 if any(item["severity"] in threshold for item in report["findings"]) else 0
        if args.command == "import-otlp":
            report = load_otlp_jsonl_detailed(args.input) if args.input_format == "jsonl" else load_otlp_json_detailed(args.input)
            write_jsonl(report["events"], args.output)
            if args.diagnostics_output:
                write_diagnostics(report, args.diagnostics_output)
            invalidating = report["summary"]["invalidating_diagnostics"]
            summary = {"events": len(report["events"]), "output": args.output, "diagnostics_output": args.diagnostics_output, "invalidating_diagnostics": invalidating}
            if args.format == "json":
                print(json.dumps(summary, indent=2, sort_keys=True))
            else:
                suffix = f"; {invalidating} diagnostic(s) may invalidate contract claims" if invalidating else ""
                print(f"Wrote {len(report['events'])} event(s) to {args.output}{suffix}")
            return 0
        if args.command == "export-otlp":
            events = load_jsonl(args.events)
            payload = convert_events_to_otlp_payload(events)
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"Wrote OTLP JSON with {len(events)} source event(s) to {args.output}")
            return 0
        if args.command == "analyze-collector-export":
            import_report = load_otlp_jsonl_detailed(args.input) if args.input_format == "jsonl" else load_otlp_json_detailed(args.input)
            report = analyze_otlp_report(import_report, cardinality_threshold=args.cardinality_threshold)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_collector_analysis_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0
        if args.command == "describe-model":
            events = load_jsonl(args.events) if args.events else None
            report = describe_model(events)
            output = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) if args.format == "json" else format_model_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0
        if args.command == "abstract-domains":
            report = summarize_abstract_domains(load_contract(args.contract), load_jsonl(args.events) if args.events else None, string_bound=args.string_bound)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_abstract_domains_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0
        if args.command == "benchmark":
            report = run_benchmark(args.config, filters={
                "case_id": args.case_id,
                "tag": args.tag,
                "check_type": args.check_type,
                "dataset": args.dataset,
                "expected_failure_mode": args.expected_failure_mode,
                "semantics_feature": args.semantics_feature,
                "service_owner": args.service_owner,
                "disclosure_status": args.disclosure_status,
            })
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0 if report["summary"]["pass"] else 1
        if args.command == "benchmark-diff":
            report = compare_benchmark_reports(args.baseline, args.candidate)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_diff_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0
        if args.command == "semconv":
            report = lint_semantic_conventions(load_contract(args.contract), load_jsonl(args.events) if args.events else None)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_semconv_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            if args.fail_on == "never":
                return 0
            return 1 if has_at_least([Finding(item["severity"], item["code"], item["message"], item["path"]) for item in report["findings"]], args.fail_on) else 0
        if args.command == "taxonomy":
            report = taxonomy_report(args.findings)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_taxonomy_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            observed = report.get("observed_findings")
            return 1 if observed and observed["summary"]["unknown_codes"] else 0
        if args.command == "sarif":
            report = report_to_sarif(json.loads(Path(args.findings).read_text(encoding="utf-8")), tool_name=args.tool_name)
            output = json.dumps(report, indent=2, sort_keys=True)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0
        if args.command == "ci-gate":
            report = evaluate_ci_gate(args.findings, args.baseline, fail_on=args.fail_on)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_ci_gate_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0 if report["summary"]["pass"] else 1
        if args.command == "ci-report":
            from .github_action import (
                analyze_for_ci,
                build_pr_comment,
                evaluate_ci_gate_for_report,
            )

            report = analyze_for_ci(args.path, service=args.service, max_files=args.max_files)
            gate = evaluate_ci_gate_for_report(
                report, min_score=args.min_score, fail_on=args.fail_on
            )
            report["gate"] = gate
            base = None
            if args.base:
                base = json.loads(Path(args.base).read_text(encoding="utf-8"))
            if args.format == "json":
                output = json.dumps(report, indent=2, sort_keys=True)
            else:
                output = build_pr_comment(report, base)
            _emit_text(output, args.output)
            return 0 if gate["pass"] else 1
        if args.command == "scorecard-badge":
            from .github_action import analyze_for_ci
            from .scorecard import (
                render_badge_svg,
                render_scorecard_svg,
                shields_endpoint_json,
            )

            if args.report:
                report = json.loads(Path(args.report).read_text(encoding="utf-8"))
            else:
                report = analyze_for_ci(args.path, service=args.service, max_files=args.max_files)
            score = report.get("diagnosability_score")
            if args.format == "shields-json":
                output = json.dumps(shields_endpoint_json(score, label=args.label), indent=2, sort_keys=True)
            elif args.format == "scorecard":
                output = render_scorecard_svg(report)
            else:
                output = render_badge_svg(score, label=args.label)
            _emit_text(output, args.output)
            return 0
        if args.command == "regenerate-artifacts":
            report = regenerate_artifacts(Path.cwd(), write=args.write)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_regeneration_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0
        if args.command == "claims-matrix":
            if args.output and args.format == "json":
                report = write_claims_evidence_matrix(args.output, Path.cwd())
                output = json.dumps(report, indent=2, sort_keys=True)
            else:
                report = claims_evidence_matrix(Path.cwd())
                if args.format == "json":
                    output = json.dumps(report, indent=2, sort_keys=True)
                else:
                    output = _format_claims_matrix_markdown(report)
                if args.output:
                    Path(args.output).write_text(output + "\n", encoding="utf-8")
            if not args.output:
                print(output)
            return 0
        if args.command == "reproduce":
            from .reproduce import check_reproduction, run_reproduction

            if args.check:
                report = check_reproduction(".")
                _emit_text(json.dumps(report, indent=2, sort_keys=True), args.output)
                return 0 if report.get("ok") else 1
            report = run_reproduction(".", write=True)
            _emit_text(json.dumps(report, indent=2, sort_keys=True), args.output)
            return 0
        if args.command == "evaluate-semantics":
            contract = load_contract(args.contract)
            report = evaluate_contract_semantics(contract, load_jsonl(args.events), strict=True if args.strict else None)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_core_semantics_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            if args.fail_on == "never":
                return 0 if report["summary"]["aligned_with_checker"] else 1
            if not report["summary"]["aligned_with_checker"]:
                return 1
            return 1 if has_at_least([Finding(item["severity"], item["code"], item["message"], item["path"]) for item in report["findings"]], args.fail_on) else 0
        if args.command == "monitor":
            contract = load_contract(args.contract)
            report = run_compiled_monitor(contract, load_jsonl(args.events))
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_monitor_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            if args.fail_on == "never":
                return 0
            return 1 if has_at_least([Finding(item["severity"], item["code"], item["message"], item["path"]) for item in report["findings"]], args.fail_on) else 0
        if args.command == "explain":
            report = explain_finding(args.code, args.examples)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_explanation_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0 if report.get("known") else 1
        if args.command == "init":
            report = scaffold_project(args.service, args.owner, args.output_dir, force=args.force)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else f"Scaffolded {args.service} telemetry contract in {report['output_dir']}"
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0
        if args.command == "doctor":
            report = run_doctor(args.collector_export, args.report_path)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_doctor_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0 if report["summary"]["pass"] else 1
        if args.command == "equivalence":
            contract = load_contract(args.contract)
            report = compare_observational_equivalence(contract, load_jsonl(args.left_events), load_jsonl(args.right_events), args.scenario or None)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_equivalence_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 1 if args.fail_on_difference and not report["equivalent"] else 0
        if args.command == "preservation":
            contract = load_contract(args.contract)
            report = check_transformation_preservation(
                contract,
                load_jsonl(args.before_events),
                load_jsonl(args.after_events),
                args.transformation or None,
                args.scenario or None,
            )
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_preservation_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            if args.fail_on == "never":
                return 0
            return 1 if has_at_least([Finding(item["severity"], item["code"], item["message"], item["path"]) for item in report["findings"]], args.fail_on) else 0
        if args.command == "refinement":
            report = check_contract_refinement(load_contract(args.base_contract), load_contract(args.candidate_contract))
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_refinement_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            if args.fail_on == "never":
                return 0
            return 1 if has_at_least([Finding(item["severity"], item["code"], item["message"], item["path"]) for item in report["findings"]], args.fail_on) else 0
        if args.command == "contract-diff":
            report = generate_contract_diff_report(load_contract(args.base_contract), load_contract(args.candidate_contract))
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_contract_diff_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            if args.fail_on == "never":
                return 0
            return 1 if has_at_least([Finding(item["severity"], item["code"], item["message"], item["path"]) for item in report["findings"]], args.fail_on) else 0
        if args.command == "compose-contract":
            report = analyze_contract_composition(args.contract)
            if args.resolved_output:
                Path(args.resolved_output).write_text(json.dumps(load_contract(args.contract), indent=2, sort_keys=True) + "\n", encoding="utf-8")
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_composition_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            if args.fail_on == "never":
                return 0
            return 1 if has_at_least([Finding(item["severity"], item["code"], item["message"], item["path"]) for item in report["findings"]], args.fail_on) else 0
        if args.command == "proof-obligations":
            contract = load_contract(args.contract)
            before_events = load_jsonl(args.before_events) if args.before_events else None
            after_events = load_jsonl(args.after_events) if args.after_events else None
            report = generate_proof_obligations_report(
                contract,
                load_jsonl(args.events) if args.events else None,
                strict=True if args.strict else None,
                source_events=before_events,
                transformed_events=after_events,
                benchmark_config=args.benchmark_config,
            )
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_proof_obligations_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 1 if args.fail_on_violated and report["summary"]["violated"] else 0
        if args.command == "report":
            contract = load_contract(args.contract)
            events = load_jsonl(args.events)
            if args.report_command == "alternative-obligations":
                report = evaluate_alternative_obligations(contract, events)
                _filter_report_findings_in_place(report, args.code, args.severity)
                serializable_report = {key: value for key, value in report.items() if key != "raw_findings"}
                output = json.dumps(serializable_report, indent=2, sort_keys=True) if args.format == "json" else format_alternative_obligations_markdown(serializable_report)
            elif args.report_command == "assume-guarantee":
                report = evaluate_assume_guarantee(contract, events)
                _filter_report_findings_in_place(report, args.code, args.severity)
                output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_assume_guarantee_markdown(report)
            elif args.report_command == "event-windows":
                report = generate_event_window_report(
                    contract,
                    events,
                    dimensions=args.dimension or None,
                    strict=True if args.strict else None,
                    incident_slice_ms=args.incident_slice_ms,
                )
                _filter_report_findings_in_place(report, args.code, args.severity)
                output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_event_window_markdown(report)
            elif args.report_command == "service-owner":
                report = generate_service_owner_report(contract, events, args.source or None, args.scenario or None)
                _filter_report_findings_in_place(report, args.code, args.severity)
                output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_service_owner_markdown(report)
            else:
                report = generate_incident_readiness_report(contract, events, args.scenario or None)
                _filter_report_findings_in_place(report, args.code, args.severity)
                output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_incident_readiness_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            if args.fail_on == "never":
                return 0
            return 1 if has_at_least([Finding(item["severity"], item["code"], item["message"], item["path"]) for item in report["findings"]], args.fail_on) else 0
        contract = load_contract(args.contract)
        if args.command == "lint-contract":
            findings = validate_contract_shape(contract)
        elif args.command == "validate":
            if getattr(args, "events_format", "native") == "auto":
                events = load_events_auto(args.events)["events"]
            else:
                events = load_jsonl(args.events)
            findings = validate_events(contract, events, strict=True if args.strict else None)
        elif args.command == "static":
            findings = check_sources(contract, [Path(item) for item in args.sources])
        elif args.command == "scenario":
            events = load_jsonl(args.events)
            findings = check_scenario(contract, events, choose_scenario(contract, args.id, args.question))
        else:  # pragma: no cover
            raise AssertionError(args.command)
    except (BenchmarkLoadError, ContractLoadError, FileNotFoundError, ValueError) as exc:
        if not hasattr(args, "fail_on"):
            print(f"ERROR input.load_error: {exc}", file=sys.stderr)
            return 2
        findings = [Finding("error", "input.load_error", str(exc), "input")]
    findings = _filter_findings(findings, getattr(args, "code", []), getattr(args, "severity", []))
    _emit_text(_format_findings(findings, args.format), getattr(args, "output", None))
    if args.fail_on == "never":
        return 0
    return 1 if has_at_least(findings, args.fail_on) else 0


def _discovery_sev_map(findings: list[dict]) -> dict[str, str]:
    rank = {"error": 0, "warning": 1, "info": 2}
    mapping: dict[str, str] = {}
    for finding in findings:
        code = finding.get("code", "")
        sev = finding.get("severity", "info")
        if code not in mapping or rank.get(sev, 3) < rank.get(mapping[code], 3):
            mapping[code] = sev
    return mapping


def _discovery_ranked_codes(report: dict) -> list[tuple[str, str, int]]:
    rank = {"error": 0, "warning": 1, "info": 2}
    by_code = report["summary"].get("by_code", {})
    sev_map = _discovery_sev_map(report["findings"])
    ranked = sorted(
        by_code.items(),
        key=lambda kv: (rank.get(sev_map.get(kv[0], "info"), 3), -kv[1], kv[0]),
    )
    return [(code, sev_map.get(code, "info"), count) for code, count in ranked]


def _format_discovery_text(report: dict, events_path: str | None = None) -> str:
    summary = report["summary"]
    rank = {"error": 0, "warning": 1, "info": 2}
    lines = [f"Analyzed {summary['events']} event(s) with no contract; {summary['findings']} finding(s)."]
    if not report["findings"]:
        lines.append("OK: no privacy or diagnosability issues detected.")
        if events_path:
            lines.append("")
            lines.append("Next steps:")
            lines.append("  - Lock this in with a starter contract:")
            lines.append(f"      python3 -m telemetry_contracts.cli infer-contract --events {events_path} > telemetry-contract.json")
        return "\n".join(lines)
    ranked = _discovery_ranked_codes(report)
    if ranked:
        width = max(len(code) for code, _, _ in ranked)
        lines.append("")
        lines.append("Top issue types:")
        for code, sev, count in ranked:
            lines.append(f"  {sev:<7} {code:<{width}}  {count}")
    lines.append("")
    lines.append("Findings (most severe first):")
    shown = sorted(
        enumerate(report["findings"]),
        key=lambda pair: (rank.get(pair[1].get("severity", ""), 3), pair[1].get("code", ""), pair[1].get("path", ""), pair[0]),
    )
    for _, finding in shown:
        location = f" at {finding.get('path')}" if finding.get("path") else ""
        lines.append(f"  {finding['severity'].upper()} {finding['code']}{location}: {finding['message']}")
    if summary["findings"] > summary["shown_findings"]:
        lines.append(f"  ... {summary['findings'] - summary['shown_findings']} more (capped per code)")
    lines.append("")
    lines.append("Next steps:")
    top = ranked[0][0] if ranked else "<code>"
    lines.append(f"  - Understand a finding:        python3 -m telemetry_contracts.cli explain {top}")
    if events_path:
        lines.append(f"  - Bootstrap a draft contract:  python3 -m telemetry_contracts.cli infer-contract --events {events_path} > telemetry-contract.json")
    return "\n".join(lines)


def _format_discovery_markdown_footer(report: dict, events_path: str | None = None) -> str:
    ranked = _discovery_ranked_codes(report)
    lines: list[str] = []
    if ranked:
        lines.extend(["", "## Top issue types", "", "| Severity | Code | Count |", "| --- | --- | ---: |"])
        for code, sev, count in ranked:
            lines.append(f"| {sev} | `{code}` | {count} |")
    lines.extend(["", "## Next steps", ""])
    if report["findings"]:
        top = ranked[0][0] if ranked else "<code>"
        lines.append(f"- Understand a finding: `explain {top}`")
        if events_path:
            lines.append(f"- Bootstrap a draft contract: `infer-contract --events {events_path}`")
    else:
        if events_path:
            lines.append(f"- Looks clean. Lock it in: `infer-contract --events {events_path}`")
    return "\n".join(lines)


def _common_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    parser.add_argument("--output", help="write command output to this path instead of stdout")
    parser.add_argument("--code", action="append", default=[], help="only include findings with this code; repeatable")
    parser.add_argument("--severity", action="append", choices=["info", "warning", "error"], default=[], help="only include findings with this severity; repeatable")


def _print_findings(findings: list[Finding], output_format: str) -> None:
    print(_format_findings(findings, output_format))


def _format_findings(findings: list[Finding], output_format: str) -> str:
    if output_format == "sarif":
        return json.dumps(findings_to_sarif([finding.to_dict() for finding in findings]), indent=2, sort_keys=True)
    if output_format == "json":
        return json.dumps({"findings": [finding.to_dict() for finding in findings], "ok": not has_at_least(findings, "error")}, indent=2, sort_keys=True)
    if not findings:
        return "OK: no findings"
    lines = []
    for finding in findings:
        location = f" at {finding.path}" if finding.path else ""
        lines.append(f"{finding.severity.upper()} {finding.code}{location}: {finding.message}")
    return "\n".join(lines)


def _emit_text(output: str, path: str | None) -> None:
    if path:
        Path(path).write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


def _filter_findings(findings: list[Finding], codes: list[str] | None, severities: list[str] | None) -> list[Finding]:
    code_set = set(codes or [])
    severity_set = set(severities or [])
    return [finding for finding in findings if (not code_set or finding.code in code_set) and (not severity_set or finding.severity in severity_set)]


def _report_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--code", action="append", default=[], help="only include report findings with this code; repeatable")
    parser.add_argument("--severity", action="append", choices=["info", "warning", "error"], default=[], help="only include report findings with this severity; repeatable")


def _filter_report_findings_in_place(report: dict, codes: list[str] | None, severities: list[str] | None) -> None:
    if not codes and not severities:
        return
    findings = report.get("findings")
    if not isinstance(findings, list):
        return
    code_set = set(codes or [])
    severity_set = set(severities or [])
    filtered = [item for item in findings if (not code_set or item.get("code") in code_set) and (not severity_set or item.get("severity") in severity_set)]
    report["findings"] = filtered
    report["applied_filters"] = {"code": sorted(code_set), "severity": sorted(severity_set)}
    summary = report.setdefault("summary", {})
    summary["findings"] = len(filtered)
    summary["findings_by_code"] = {key: sum(1 for item in filtered if item.get("code") == key) for key in sorted({item.get("code") for item in filtered})}
    summary["findings_by_severity"] = {key: sum(1 for item in filtered if item.get("severity") == key) for key in sorted({item.get("severity") for item in filtered})}
    if "pass" in summary:
        summary["pass"] = not any(item.get("severity") == "error" for item in filtered)


def _format_claims_matrix_markdown(report: dict) -> str:
    lines = ["# Claims-to-evidence matrix", "", "| Claim | Evidence | Tests | Limitations |", "| --- | --- | --- | --- |"]
    for claim in report["claims"]:
        evidence = ", ".join(f"`{item}`" for item in claim["public_artifacts"] + claim["fixtures"])
        tests = ", ".join(f"`{item}`" for item in claim["tests"])
        limitations = "<br>".join(claim["limitations"])
        lines.append(f"| {claim['claim']} | {evidence} | {tests} | {limitations} |")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
