from __future__ import annotations

import json
from typing import Any

from .findings import Finding, has_at_least
from .validator import _MISSING, _lookup_field

ALTERNATIVE_OBLIGATION_MODEL = {
    "name": "alternative-obligations-v1",
    "relation": (
        "A required alternative obligation A is satisfied by finite trace T when at least "
        "one declared option has a concrete witness event in T containing every field "
        "listed for that option. Optional alternatives document acceptable evidence paths "
        "but do not make T fail when no option is witnessed. This is an executable "
        "finite disjunction: T ⊨ A iff required(A)=false or ∃ option,witness. option(witness)."
    ),
}


def evaluate_alternative_obligations(contract: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    groups = _alternative_groups(contract)
    evaluations: list[dict[str, Any]] = []
    findings: list[Finding] = []
    service = contract.get("service")
    relevant_events = [event for event in events if service is None or event.get("service") in {service, None}]
    for index, group in enumerate(groups):
        evaluation = _evaluate_group(group, index, relevant_events)
        evaluations.append(evaluation)
        if evaluation["required"] and not evaluation["satisfied"]:
            findings.append(
                Finding(
                    "error",
                    "telemetry.alternative_missing",
                    f"alternative obligation '{evaluation['id']}' has no satisfied evidence option",
                    "events",
                    evaluation["contract_path"],
                    details={
                        "model": ALTERNATIVE_OBLIGATION_MODEL["name"],
                        "options": [
                            {
                                "signal": option.get("signal"),
                                "name": option.get("name"),
                                "status": option.get("status"),
                                "missing_fields": option.get("missing_fields", []),
                                "matching_event_indices": option.get("matching_event_indices", []),
                            }
                            for option in evaluation["options"]
                        ],
                    },
                )
            )
    return {
        "model": ALTERNATIVE_OBLIGATION_MODEL,
        "service": contract.get("service", ""),
        "summary": {
            "groups": len(evaluations),
            "required_groups": sum(1 for item in evaluations if item["required"]),
            "satisfied_groups": sum(1 for item in evaluations if item["satisfied"]),
            "unsatisfied_required_groups": sum(1 for item in evaluations if item["required"] and not item["satisfied"]),
            "pass": not has_at_least(findings, "error"),
        },
        "alternative_obligations": evaluations,
        "findings": [finding.to_dict() for finding in findings],
        "raw_findings": findings,
    }


def alternative_obligation_findings(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    return evaluate_alternative_obligations(contract, events)["raw_findings"]


def format_alternative_obligations_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Alternative-obligations report: {report.get('service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Groups: {summary['groups']}",
        f"- Required groups: {summary['required_groups']}",
        f"- Satisfied groups: {summary['satisfied_groups']}",
        f"- Unsatisfied required groups: {summary['unsatisfied_required_groups']}",
        "",
        "## Relation",
        "",
        report["model"]["relation"],
        "",
        "## Obligations",
        "",
    ]
    if not report["alternative_obligations"]:
        lines.append("No alternative obligations are declared.")
    for group in report["alternative_obligations"]:
        lines.extend(
            [
                f"### `{group['id']}`",
                "",
                f"- Required: `{str(group['required']).lower()}`",
                f"- Satisfied: `{str(group['satisfied']).lower()}`",
                f"- Winning option: `{group.get('winning_option') or 'none'}`",
            ]
        )
        if group.get("purpose"):
            lines.append(f"- Purpose: {group['purpose']}")
        lines.append("- Options:")
        for option in group["options"]:
            missing = ", ".join(option.get("missing_fields", [])) or "none"
            lines.append(
                f"  - `{option['id']}` {option['signal']} `{option['name']}`: "
                f"{option['status']} (matches={option['matching_event_indices']}, missing_fields={missing})"
            )
        lines.append("")
    if report.get("findings"):
        lines.extend(["## Findings", ""])
        for finding in report["findings"]:
            lines.append(f"- **{finding['severity']} `{finding['code']}`**: {finding['message']}")
            if finding.get("details"):
                lines.append(f"  - Details: `{json.dumps(finding['details'], sort_keys=True)}`")
        lines.append("")
    return "\n".join(lines)


def evaluate_alternative_requirement(requirement: dict[str, Any], events: list[dict[str, Any]], contract_path: str) -> dict[str, Any]:
    options = requirement.get("any_of")
    if not isinstance(options, list) or not options:
        return {
            "status": "malformed",
            "satisfied": False,
            "contract_path": contract_path,
            "options": [],
            "missing_fields": [],
            "observed_fields": [],
            "matching_event_indices": [],
        }
    option_results = [_evaluate_option(option, option_index, events, f"{contract_path}.any_of[{option_index}]") for option_index, option in enumerate(options)]
    winner = next((option for option in option_results if option["satisfied"]), None)
    best = winner or _best_unsatisfied_option(option_results)
    return {
        "status": "satisfied" if winner else "unsatisfied",
        "satisfied": winner is not None,
        "signal": "alternative",
        "name": str(requirement.get("id") or requirement.get("purpose") or "any_of"),
        "purpose": requirement.get("purpose", ""),
        "fields": best.get("fields", []) if best else [],
        "contract_path": contract_path,
        "evidence_path": f"events[alternative={requirement.get('id', 'any_of')}]",
        "matching_event_indices": best.get("matching_event_indices", []) if best else [],
        "observed_fields": best.get("observed_fields", []) if best else [],
        "missing_fields": best.get("missing_fields", []) if best else [],
        "winning_option": winner.get("id") if winner else None,
        "options": option_results,
    }


def _alternative_groups(contract: dict[str, Any]) -> list[dict[str, Any]]:
    raw = contract.get("alternative_obligations", []) or []
    return [group for group in raw if isinstance(group, dict)] if isinstance(raw, list) else []


def _evaluate_group(group: dict[str, Any], index: int, events: list[dict[str, Any]]) -> dict[str, Any]:
    path = f"$.alternative_obligations[{index}]"
    options = group.get("any_of", [])
    option_results = []
    if isinstance(options, list):
        option_results = [_evaluate_option(option, option_index, events, f"{path}.any_of[{option_index}]") for option_index, option in enumerate(options)]
    winner = next((option for option in option_results if option["satisfied"]), None)
    return {
        "id": str(group.get("id") or index),
        "purpose": group.get("purpose") or group.get("description") or "",
        "required": group.get("required", True) is not False,
        "satisfied": winner is not None,
        "winning_option": winner.get("id") if winner else None,
        "contract_path": path,
        "options": option_results,
    }


def _evaluate_option(option: Any, index: int, events: list[dict[str, Any]], contract_path: str) -> dict[str, Any]:
    if not isinstance(option, dict):
        return {
            "id": str(index),
            "signal": "",
            "name": "",
            "fields": [],
            "contract_path": contract_path,
            "matching_event_indices": [],
            "observed_fields": [],
            "missing_fields": [],
            "status": "malformed",
            "satisfied": False,
        }
    signal = _normalize_signal_kind(option.get("signal", option.get("kind")))
    name = option.get("name")
    fields = [str(field) for field in option.get("fields", []) or [] if isinstance(field, str) and field]
    matches = [(event_index, event) for event_index, event in enumerate(events) if event.get("kind") == signal and event.get("name") == name]
    observed_fields = sorted({field for _, event in matches for field in fields if _lookup_field(event, field)[0] is not _MISSING})
    witness_index = None
    for event_index, event in matches:
        if all(_lookup_field(event, field)[0] is not _MISSING for field in fields):
            witness_index = event_index
            break
    missing_fields = sorted(field for field in fields if field not in observed_fields)
    if witness_index is not None:
        status = "satisfied"
    elif matches:
        status = "missing-fields"
    else:
        status = "missing-signal"
    return {
        "id": str(option.get("id") or f"{signal}:{name}"),
        "signal": signal,
        "name": name if isinstance(name, str) else "",
        "fields": fields,
        "contract_path": contract_path,
        "evidence_path": f"events[{signal}={name}]",
        "matching_event_indices": [event_index for event_index, _ in matches],
        "witness_event_index": witness_index,
        "observed_fields": observed_fields,
        "missing_fields": missing_fields,
        "status": status,
        "satisfied": witness_index is not None,
    }


def _best_unsatisfied_option(options: list[dict[str, Any]]) -> dict[str, Any]:
    if not options:
        return {}
    return max(options, key=lambda item: (len(item.get("matching_event_indices", [])) > 0, len(item.get("observed_fields", []))))


def _normalize_signal_kind(value: Any) -> str:
    return {"spans": "span", "logs": "log", "metrics": "metric"}.get(str(value), str(value))
