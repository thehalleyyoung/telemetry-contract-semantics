"""Execution semantics + observability-as-correctness for *existing* projects.

This module bridges two ideas onto arbitrary telemetry you already have:

* "Inferring execution semantics" — from raw events we infer a draft contract
  and an observed execution order (a partial order over signals), then run the
  small-step semantics evaluator (``evaluate_contract_semantics``) to produce a
  formal derivation and an observed event-structure model.
* "Observability as a correctness property" — the inferred contract turns the
  question "is this trace well-formed / consistently ordered?" into a checkable
  correctness judgement, without requiring the project to adopt our labels.

Everything here is pure stdlib and deterministic.
"""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

from .core_semantics import evaluate_contract_semantics
from .infer import infer_contract, infer_temporal_order
from .static_checker import SOURCE_SUFFIXES, check_sources

SCHEMA = "telemetry-contracts/execution-semantics@1"

_MAX_SOURCE_FILES = 20000
_SOURCE_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "venv", ".venv",
    "__pycache__", ".mypy_cache", ".pytest_cache", "dist", "build",
    "target", ".tox", ".idea", ".vscode", "site-packages",
}


def infer_execution_semantics(
    events: list[dict[str, Any]],
    *,
    service: str | None = None,
    infer_sequences: bool = True,
    strict: bool = False,
) -> dict[str, Any]:
    """Infer a contract and derive its execution semantics for raw events."""

    contract = infer_contract(events, service=service, infer_sequences=infer_sequences)
    evaluation = evaluate_contract_semantics(contract, events, strict=strict)
    order = infer_temporal_order(events) if infer_sequences else None

    structure = evaluation["event_structure"]
    summary = evaluation["summary"]
    return {
        "schema": SCHEMA,
        "service": contract.get("service"),
        "inferred_contract": contract,
        "semantics": {
            "model": evaluation["model"]["name"],
            "judgement": evaluation["model"]["judgement"],
            "pass": summary["pass"],
            "aligned_with_checker": summary["aligned_with_checker"],
            "events": summary["events"],
            "relevant_events": summary["relevant_events"],
            "small_steps": summary["steps"],
            "findings_by_severity": summary["findings_by_severity"],
            "findings_by_code": summary["findings_by_code"],
        },
        "inferred_ordering": order,
        "event_structure": {
            "node_count": structure["node_count"],
            "edge_count": structure["edge_count"],
            "concurrency_pair_count": structure["concurrency_pair_count"],
            "incident_window_count": len(structure["incident_windows"]),
        },
        "small_steps": evaluation["small_steps"],
        "findings": evaluation["findings"],
    }


def semantics_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Condense a full ``infer_execution_semantics`` report for scan output."""

    order = report.get("inferred_ordering")
    ordering_summary: dict[str, Any] | None = None
    if order:
        ordering_summary = {
            "correlation_key": order["correlation_key"],
            "steps": [f"{step['kind']}:{step['name']}" for step in order["steps"]],
            "enforceable": order["enforceable"],
            "support_full_groups": order["support_full_groups"],
            "partial_groups": order["partial_groups"],
            "window_ms": order.get("window_ms"),
        }
    semantics = report["semantics"]
    return {
        "service": report.get("service"),
        "pass": semantics["pass"],
        "aligned_with_checker": semantics["aligned_with_checker"],
        "relevant_events": semantics["relevant_events"],
        "small_steps": semantics["small_steps"],
        "findings_by_code": semantics["findings_by_code"],
        "inferred_ordering": ordering_summary,
        "event_structure": report["event_structure"],
    }


def find_source_files(root: str, *, max_files: int = _MAX_SOURCE_FILES) -> list[str]:
    """Bounded, pruned walk for source files (for runtime/source alignment)."""

    found: list[str] = []
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in _SOURCE_SKIP_DIRS)
        for filename in sorted(filenames):
            seen += 1
            if seen > max_files:
                dirnames[:] = []
                break
            if os.path.splitext(filename)[1].lower() in SOURCE_SUFFIXES:
                found.append(os.path.join(dirpath, filename))
        if seen > max_files:
            break
    found.sort()
    return found


def align_runtime_with_source(
    contract: dict[str, Any], source_files: list[str]
) -> dict[str, Any]:
    """Informational runtime-name vs source-literal alignment.

    Runtime signal names frequently differ from source string literals (helper
    wrappers, constants, semantic-convention/auto-instrumentation), so a missing
    name is a *hint*, never an error. We never drive an exit code from this.
    """

    expectations: dict[str, list[str]] = {
        section: sorted({signal["name"] for signal in contract.get(section, [])})
        for section in ("spans", "metrics", "logs")
        if contract.get(section)
    }
    expected_names = sorted({name for names in expectations.values() for name in names})
    if not expected_names or not source_files:
        return {
            "expected_signals": len(expected_names),
            "source_files": len(source_files),
            "located_in_source": [],
            "not_located_in_source": expected_names,
            "note": "informational only; runtime names often differ from source literals",
        }

    probe = dict(contract)
    probe["static_expectations"] = expectations
    findings = check_sources(probe, source_files)
    not_located = sorted(
        {
            finding.details.get("name")
            for finding in findings
            if finding.code == "static.missing_instrumentation"
            and finding.details
            and finding.details.get("name")
        }
    )
    located = [name for name in expected_names if name not in set(not_located)]
    return {
        "expected_signals": len(expected_names),
        "source_files": len(source_files),
        "located_in_source": located,
        "not_located_in_source": not_located,
        "note": "informational only; runtime names often differ from source literals",
    }


def group_events_by_service(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        service = event.get("service")
        key = service if isinstance(service, str) and service else "(unspecified)"
        grouped[key].append(event)
    return dict(grouped)


def format_semantics_text(report: dict[str, Any]) -> str:
    semantics = report["semantics"]
    lines: list[str] = []
    service = report.get("service") or "(unspecified)"
    lines.append(f"Execution semantics for service: {service}")
    lines.append(f"  model: {semantics['model']}  {semantics['judgement']}")
    verdict = "consistent" if semantics["pass"] else "inconsistent"
    lines.append(
        f"  derivation: {semantics['small_steps']} small steps over "
        f"{semantics['relevant_events']} relevant events -> {verdict}"
    )
    lines.append(
        f"  aligned with checker: {'yes' if semantics['aligned_with_checker'] else 'no'}"
    )
    structure = report["event_structure"]
    lines.append(
        f"  event structure: {structure['node_count']} nodes, "
        f"{structure['edge_count']} happens-before edges, "
        f"{structure['concurrency_pair_count']} concurrent pairs"
    )
    order = report.get("inferred_ordering")
    if order:
        chain = " -> ".join(f"{step['kind']}:{step['name']}" for step in order["steps"])
        lines.append(f"  inferred order ({order['correlation_key']}): {chain}")
        status = "enforceable" if order["enforceable"] else "candidate (not enforced)"
        lines.append(
            f"    {status}; supported by {order['support_full_groups']} groups, "
            f"{order['partial_groups']} partial"
        )
    else:
        lines.append("  inferred order: none (insufficient correlated evidence)")
    by_code = semantics["findings_by_code"]
    if by_code:
        top = sorted(by_code.items(), key=lambda item: (-item[1], item[0]))
        rollup = ", ".join(f"{code}={count}" for code, count in top)
        lines.append(f"  findings: {rollup}")
    else:
        lines.append("  findings: none")
    return "\n".join(lines)


def format_semantics_markdown(report: dict[str, Any]) -> str:
    semantics = report["semantics"]
    service = report.get("service") or "(unspecified)"
    lines: list[str] = []
    lines.append(f"## Execution semantics — `{service}`")
    lines.append("")
    lines.append(f"- **Model:** `{semantics['model']}` — {semantics['judgement']}")
    verdict = "consistent" if semantics["pass"] else "inconsistent"
    lines.append(
        f"- **Derivation:** {semantics['small_steps']} small steps over "
        f"{semantics['relevant_events']} relevant events → **{verdict}**"
    )
    lines.append(
        f"- **Aligned with checker:** {'yes' if semantics['aligned_with_checker'] else 'no'}"
    )
    structure = report["event_structure"]
    lines.append(
        f"- **Event structure:** {structure['node_count']} nodes, "
        f"{structure['edge_count']} happens-before edges, "
        f"{structure['concurrency_pair_count']} concurrent pairs"
    )
    order = report.get("inferred_ordering")
    if order:
        chain = " → ".join(f"`{step['kind']}:{step['name']}`" for step in order["steps"])
        status = "enforceable" if order["enforceable"] else "candidate (not enforced)"
        lines.append(
            f"- **Inferred order** (`{order['correlation_key']}`): {chain} "
            f"— _{status}; {order['support_full_groups']} supporting groups, "
            f"{order['partial_groups']} partial_"
        )
    else:
        lines.append("- **Inferred order:** none (insufficient correlated evidence)")
    by_code = semantics["findings_by_code"]
    if by_code:
        lines.append("")
        lines.append("| Finding | Count |")
        lines.append("| --- | ---: |")
        for code, count in sorted(by_code.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"| `{code}` | {count} |")
    return "\n".join(lines)
