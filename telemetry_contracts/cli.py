from __future__ import annotations

import argparse
import json
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
from .sarif import findings_to_sarif, report_to_sarif
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
    scan_parser.add_argument("--path", required=True, help="project directory to scan for telemetry/log files")
    scan_parser.add_argument("--service", help="only analyze events from this service")
    scan_parser.add_argument("--max-files", type=int, default=300, help="maximum candidate files to scan")
    scan_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    scan_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    scan_parser.add_argument("--output", help="write command output to this path instead of stdout")

    scan_repo_parser = subparsers.add_parser("scan-repo", help="download a GitHub repository and analyze whatever telemetry it ships, in any format")
    scan_repo_parser.add_argument("--repo", required=True, help="GitHub 'owner/repo' or a full https/git clone URL")
    scan_repo_parser.add_argument("--ref", help="branch or tag to clone (defaults to the repository's default branch)")
    scan_repo_parser.add_argument("--service", help="only analyze events from this service")
    scan_repo_parser.add_argument("--max-files", type=int, default=300, help="maximum candidate files to scan")
    scan_repo_parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    scan_repo_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")
    scan_repo_parser.add_argument("--output", help="write command output to this path instead of stdout")

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

    regenerate_parser = subparsers.add_parser("regenerate-artifacts", help="list or write deterministic report regeneration artifacts")
    regenerate_parser.add_argument("--write", action="store_true", help="write reports/current_impact*, reports/paper_tables.md, and docs/claims_evidence_matrix.json")
    regenerate_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    regenerate_parser.add_argument("--output")

    claims_parser = subparsers.add_parser("claims-matrix", help="emit README/report claim-to-evidence mapping")
    claims_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    claims_parser.add_argument("--output")

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
                output = format_discovery_markdown(report)
            else:
                output = _format_discovery_text(report)
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
        if args.command in {"scan", "scan-repo"}:
            try:
                if args.command == "scan":
                    report = scan_directory(args.path, service=args.service, max_files=args.max_files)
                else:
                    report = scan_repo(args.repo, ref=args.ref, service=args.service, max_files=args.max_files)
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


def _format_discovery_text(report: dict) -> str:
    summary = report["summary"]
    lines = [f"Analyzed {summary['events']} event(s) with no contract; {summary['findings']} finding(s)."]
    if not report["findings"]:
        lines.append("OK: no privacy or diagnosability issues detected.")
        return "\n".join(lines)
    for finding in report["findings"]:
        location = f" at {finding.get('path')}" if finding.get("path") else ""
        lines.append(f"{finding['severity'].upper()} {finding['code']}{location}: {finding['message']}")
    if summary["findings"] > summary["shown_findings"]:
        lines.append(f"... {summary['findings'] - summary['shown_findings']} more (capped per code)")
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
