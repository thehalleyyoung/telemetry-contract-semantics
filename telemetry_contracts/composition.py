from __future__ import annotations

import json
import copy
from collections import Counter
from pathlib import Path
from typing import Any

from .findings import Finding, has_at_least
from .loader import composition_parents, load_contract_raw, load_contract_with_composition
from .refinement import check_contract_refinement


COMPOSITION_MODEL = {
    "name": "contract-composition-v1",
    "notation": "C = P₁ ⊕ … ⊕ Pₙ ⊕ Δ",
    "relation": (
        "A composed contract is the left-to-right merge of inherited organization/team policies "
        "and the service delta. Each parent policy must be refined by the resolved child contract, "
        "so inherited required evidence, privacy policies, strict-mode assumptions, temporal/scenario "
        "obligations, and assume-guarantee clauses are not silently weakened."
    ),
    "clauses": ["COMP.merge-denotation", "COMP.parent-refinement", "REF.requirement-preservation"],
}


def analyze_contract_composition(path: str | Path) -> dict[str, Any]:
    loaded = load_contract_with_composition(path)
    contract = loaded["contract"]
    evidence = _relativize_paths(loaded["composition"])
    raw = load_contract_raw(path)
    direct_parent_reports = []
    findings: list[dict[str, Any]] = []
    for parent_ref in composition_parents(raw):
        parent_path = (Path(path).resolve().parent / parent_ref).resolve()
        parent_contract = load_contract_with_composition(parent_path)["contract"]
        refinement_report = check_contract_refinement(parent_contract, contract)
        direct_parent_reports.append(
            {
                "path": _display_path(parent_path),
                "service": parent_contract.get("service", ""),
                "refines_parent": refinement_report["summary"]["refines"],
                "findings": refinement_report["findings"],
                "required_signals_preserved": refinement_report.get("evidence", {}).get("required_signals_preserved", []),
            }
        )
        findings.extend(refinement_report["findings"])
    return {
        "model": COMPOSITION_MODEL,
        "contract_path": _display_path(Path(path).resolve()),
        "service": contract.get("service", ""),
        "summary": {
            "has_composition": evidence["has_composition"],
            "valid": not has_at_least([_finding_from_dict(item) for item in findings], "error"),
            "direct_parents": len(direct_parent_reports),
            "inherited_signals": len(evidence.get("inherited_signal_keys", [])),
            "declared_signals": len(evidence.get("declared_signal_keys", [])),
            "resolved_signals": len(evidence.get("resolved_signal_keys", [])),
            "overridden_signals": len(evidence.get("overridden_signal_keys", [])),
            "findings": len(findings),
            "findings_by_code": dict(sorted(Counter(item["code"] for item in findings).items())),
        },
        "composition": evidence,
        "parent_refinement_reports": direct_parent_reports,
        "findings": findings,
        "limitations": [
            "Composition is finite JSON/YAML contract inheritance; it is not a theorem prover for arbitrary policy languages.",
            "Weakening detection reuses the deterministic refinement checker, whose predicate implication checks are conservative for regexes and arbitrary predicates.",
            "Historical case-study composition reports validate checked-in reconstructed contracts and public facts, not private production policy history.",
        ],
    }


def format_composition_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Contract-composition report: {report.get('service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Notation: `{report['model']['notation']}`",
        f"- Has inherited policies: `{str(summary['has_composition']).lower()}`",
        f"- Composition valid: `{str(summary['valid']).lower()}`",
        f"- Direct parents: {summary['direct_parents']}",
        f"- Inherited signals: {summary['inherited_signals']}",
        f"- Declared signals: {summary['declared_signals']}",
        f"- Resolved signals: {summary['resolved_signals']}",
        f"- Overridden signals: {summary['overridden_signals']}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        "",
        "## Relation",
        "",
        report["model"]["relation"],
        "",
        "## Inheritance evidence",
        "",
        f"- Inherited signal keys: `{json.dumps(report['composition'].get('inherited_signal_keys', []), sort_keys=True)}`",
        f"- Declared signal keys: `{json.dumps(report['composition'].get('declared_signal_keys', []), sort_keys=True)}`",
        f"- Overridden signal keys: `{json.dumps(report['composition'].get('overridden_signal_keys', []), sort_keys=True)}`",
        "",
        "## Parent refinement checks",
        "",
    ]
    if not report["parent_refinement_reports"]:
        lines.append("No parent contracts are declared.")
    for parent in report["parent_refinement_reports"]:
        lines.append(f"- `{parent['path']}` refines parent: `{str(parent['refines_parent']).lower()}`; findings: {len(parent['findings'])}")
    lines.extend(["", "## Findings", ""])
    if not report["findings"]:
        lines.append("No parent-refinement violations were found.")
    for finding in report["findings"]:
        lines.append(f"- **{finding['severity']} `{finding['code']}`** at `{finding['path']}`: {finding['message']}")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines).rstrip()


def _finding_from_dict(item: dict[str, Any]) -> Finding:
    return Finding(item["severity"], item["code"], item["message"], item.get("path", ""), item.get("contract_path"), item.get("event_index"), item.get("details"))


def _relativize_paths(value: Any) -> Any:
    result = copy.deepcopy(value)
    if isinstance(result, dict):
        for key, child in list(result.items()):
            if key == "path" and isinstance(child, str):
                result[key] = _display_path(Path(child))
            else:
                result[key] = _relativize_paths(child)
    elif isinstance(result, list):
        result = [_relativize_paths(item) for item in result]
    return result


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)
