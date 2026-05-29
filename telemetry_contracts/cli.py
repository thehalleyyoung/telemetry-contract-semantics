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
from .benchmark import BenchmarkLoadError, format_markdown, run_benchmark
from .taxonomy import format_taxonomy_markdown, taxonomy_report
from .validator import validate_contract_shape, validate_events
from .equivalence import compare_observational_equivalence, format_equivalence_markdown


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

    benchmark_parser = subparsers.add_parser("benchmark", help="run a benchmark suite from a JSON config")
    benchmark_parser.add_argument("--config", default="benchmarks/builtin.json")
    benchmark_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    benchmark_parser.add_argument("--output")

    taxonomy_parser = subparsers.add_parser("taxonomy", help="emit the machine-readable finding taxonomy and optional observed finding coverage")
    taxonomy_parser.add_argument("--findings", action="append", default=[], help="JSON report containing findings or benchmark cases with findings")
    taxonomy_parser.add_argument("--format", choices=["json", "markdown"], default="json")
    taxonomy_parser.add_argument("--output")

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
        if args.command == "report":
            contract = load_contract(args.contract)
            events = load_jsonl(args.events)
            if args.report_command == "alternative-obligations":
                report = evaluate_alternative_obligations(contract, events)
                serializable_report = {key: value for key, value in report.items() if key != "raw_findings"}
                output = json.dumps(serializable_report, indent=2, sort_keys=True) if args.format == "json" else format_alternative_obligations_markdown(serializable_report)
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
