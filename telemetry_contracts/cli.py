from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .findings import Finding, has_at_least
from .incident_report import format_incident_readiness_markdown, generate_incident_readiness_report
from .loader import ContractLoadError, load_contract, load_jsonl
from .otlp import load_otlp_json, write_jsonl
from .scenario import check_scenario, choose_scenario
from .semantics import describe_model, format_model_markdown
from .preservation import check_transformation_preservation, format_preservation_markdown
from .static_checker import check_sources
from .alternatives import evaluate_alternative_obligations, format_alternative_obligations_markdown
from .assume_guarantee import evaluate_assume_guarantee, format_assume_guarantee_markdown
from .benchmark import BenchmarkLoadError, format_markdown, run_benchmark
from .core_semantics import evaluate_contract_semantics, format_core_semantics_markdown
from .taxonomy import format_taxonomy_markdown, taxonomy_report
from .explain import explain_finding, format_explanation_markdown
from .validator import validate_contract_shape, validate_events
from .equivalence import compare_observational_equivalence, format_equivalence_markdown
from .proof_obligations import format_proof_obligations_markdown, generate_proof_obligations_report
from .refinement import check_contract_refinement, format_refinement_markdown
from .composition import analyze_contract_composition, format_composition_markdown
from .monitor import format_monitor_markdown, run_compiled_monitor
from .windows import format_event_window_markdown, generate_event_window_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="telemetry-contracts", description="Validate telemetry contracts against events and source code.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate JSONL telemetry against a contract")
    validate_parser.add_argument("--contract", required=True)
    validate_parser.add_argument("--events", required=True)
    validate_parser.add_argument("--strict", action="store_true", help="also reject unmodeled services, undeclared signals, unexpected fields, and undocumented transformations")
    _common_output_args(validate_parser)

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

    otlp_parser = subparsers.add_parser("import-otlp", help="convert OTLP JSON export to telemetry-contracts JSONL")
    otlp_parser.add_argument("--input", required=True)
    otlp_parser.add_argument("--output", required=True)

    model_parser = subparsers.add_parser("describe-model", help="describe the observation domain and satisfaction relation")
    model_parser.add_argument("--events", help="optional JSONL artifact to summarize against the observation model")
    model_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    model_parser.add_argument("--output")

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

    taxonomy_parser = subparsers.add_parser("taxonomy", help="emit the machine-readable finding taxonomy and optional observed finding coverage")
    taxonomy_parser.add_argument("--findings", action="append", default=[], help="JSON report containing findings or benchmark cases with findings")
    taxonomy_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    taxonomy_parser.add_argument("--output")

    explain_parser = subparsers.add_parser("explain", help="explain a finding code with formal meaning, impact, examples, and fixes")
    explain_parser.add_argument("code", help="finding code such as telemetry.missing_field")
    explain_parser.add_argument("--examples", action="append", default=[], help="JSON finding report to mine for concrete observed examples")
    explain_parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    explain_parser.add_argument("--output")

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

    alternative_parser = report_subparsers.add_parser("alternative-obligations", help="explain disjunctive evidence obligations and witnesses")
    alternative_parser.add_argument("--contract", required=True)
    alternative_parser.add_argument("--events", required=True)
    alternative_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    alternative_parser.add_argument("--output")
    alternative_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    ag_parser = report_subparsers.add_parser("assume-guarantee", help="partition telemetry obligations by service, collector, environment, and on-call layers")
    ag_parser.add_argument("--contract", required=True)
    ag_parser.add_argument("--events", required=True)
    ag_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    ag_parser.add_argument("--output")
    ag_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    windows_parser = report_subparsers.add_parser("event-windows", help="group events and findings by trace, request, tenant, deployment, scenario, and incident slices")
    windows_parser.add_argument("--contract", required=True)
    windows_parser.add_argument("--events", required=True)
    windows_parser.add_argument("--dimension", action="append", default=[], help="window dimension: trace, request, tenant, deployment, scenario, incident, or all")
    windows_parser.add_argument("--incident-slice-ms", type=int, help="also group events into bounded incident time slices")
    windows_parser.add_argument("--strict", action="store_true", help="include strict closed-world validation findings before grouping")
    windows_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    windows_parser.add_argument("--output")
    windows_parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")

    args = parser.parse_args(argv)
    try:
        if args.command == "import-otlp":
            events = load_otlp_json(args.input)
            write_jsonl(events, args.output)
            print(f"Wrote {len(events)} event(s) to {args.output}")
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
        if args.command == "benchmark":
            report = run_benchmark(args.config)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0 if report["summary"]["pass"] else 1
        if args.command == "taxonomy":
            report = taxonomy_report(args.findings)
            output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_taxonomy_markdown(report)
            if args.output:
                Path(args.output).write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            observed = report.get("observed_findings")
            return 1 if observed and observed["summary"]["unknown_codes"] else 0
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
                serializable_report = {key: value for key, value in report.items() if key != "raw_findings"}
                output = json.dumps(serializable_report, indent=2, sort_keys=True) if args.format == "json" else format_alternative_obligations_markdown(serializable_report)
            elif args.report_command == "assume-guarantee":
                report = evaluate_assume_guarantee(contract, events)
                output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_assume_guarantee_markdown(report)
            elif args.report_command == "event-windows":
                report = generate_event_window_report(
                    contract,
                    events,
                    dimensions=args.dimension or None,
                    strict=True if args.strict else None,
                    incident_slice_ms=args.incident_slice_ms,
                )
                output = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else format_event_window_markdown(report)
            else:
                report = generate_incident_readiness_report(contract, events, args.scenario or None)
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
            findings = validate_events(contract, load_jsonl(args.events), strict=True if args.strict else None)
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
    _print_findings(findings, args.format)
    if args.fail_on == "never":
        return 0
    return 1 if has_at_least(findings, args.fail_on) else 0


def _common_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--fail-on", choices=["error", "warning", "never"], default="error")


def _print_findings(findings: list[Finding], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps({"findings": [finding.to_dict() for finding in findings], "ok": not has_at_least(findings, "error")}, indent=2, sort_keys=True))
        return
    if not findings:
        print("OK: no findings")
        return
    for finding in findings:
        location = f" at {finding.path}" if finding.path else ""
        print(f"{finding.severity.upper()} {finding.code}{location}: {finding.message}")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
