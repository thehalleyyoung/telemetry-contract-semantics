from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .findings import Finding, has_at_least
from .loader import ContractLoadError, load_contract, load_jsonl
from .otlp import load_otlp_json, write_jsonl
from .scenario import check_scenario, choose_scenario
from .static_checker import check_sources
from .validator import validate_events


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="telemetry-contracts", description="Validate telemetry contracts against events and source code.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="validate JSONL telemetry against a contract")
    validate_parser.add_argument("--contract", required=True)
    validate_parser.add_argument("--events", required=True)
    _common_output_args(validate_parser)

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

    args = parser.parse_args(argv)
    try:
        if args.command == "import-otlp":
            events = load_otlp_json(args.input)
            write_jsonl(events, args.output)
            print(f"Wrote {len(events)} event(s) to {args.output}")
            return 0
        contract = load_contract(args.contract)
        if args.command == "validate":
            findings = validate_events(contract, load_jsonl(args.events))
        elif args.command == "static":
            findings = check_sources(contract, [Path(item) for item in args.sources])
        elif args.command == "scenario":
            events = load_jsonl(args.events)
            findings = check_scenario(contract, events, choose_scenario(contract, args.id, args.question))
        else:  # pragma: no cover
            raise AssertionError(args.command)
    except (ContractLoadError, FileNotFoundError, ValueError) as exc:
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
