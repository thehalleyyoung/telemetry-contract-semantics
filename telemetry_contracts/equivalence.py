from __future__ import annotations

from typing import Any

from .scenario import evaluate_scenario_adequacy

OBSERVATIONAL_EQUIVALENCE_MODEL = {
    "name": "observational-equivalence-v1",
    "relation": (
        "Two finite telemetry traces are observationally equivalent for a declared "
        "debugging task when the diagnosability answer signature for every "
        "selected incident question is identical: the same questions are answerable, "
        "the same minimum observations are witnessed, and the same required fields "
        "are present or absent. Extra events, event order, concrete values, and byte "
        "representation are ignored unless they change that question-level signature."
    ),
}


def compare_observational_equivalence(
    contract: dict[str, Any],
    left_events: list[dict[str, Any]],
    right_events: list[dict[str, Any]],
    scenario_ids: list[str] | None = None,
) -> dict[str, Any]:
    scenarios = _selected_scenarios(contract, scenario_ids)
    comparisons = []
    equivalent = True
    for scenario in scenarios:
        left = evaluate_scenario_adequacy(contract, left_events, scenario)
        right = evaluate_scenario_adequacy(contract, right_events, scenario)
        left_signature = _answer_signature(left)
        right_signature = _answer_signature(right)
        deltas = _signature_deltas(left_signature, right_signature)
        if deltas:
            equivalent = False
        comparisons.append(
            {
                "id": scenario.get("id", ""),
                "question": scenario.get("question", ""),
                "equivalent": not deltas,
                "left_answerable": left["answerable"],
                "right_answerable": right["answerable"],
                "left_signature": left_signature,
                "right_signature": right_signature,
                "deltas": deltas,
            }
        )
    if not scenarios:
        equivalent = False
    return {
        "model": OBSERVATIONAL_EQUIVALENCE_MODEL,
        "service": contract.get("service", ""),
        "equivalent": equivalent,
        "summary": {
            "questions_compared": len(comparisons),
            "equivalent_questions": sum(1 for item in comparisons if item["equivalent"]),
            "different_questions": sum(1 for item in comparisons if not item["equivalent"]),
            "left_events": len(left_events),
            "right_events": len(right_events),
        },
        "comparisons": comparisons,
        "limitations": [
            "Equivalence is scoped to selected contract scenarios and their declared minimum observations.",
            "This relation compares question answerability signatures, not raw values or byte equality.",
            "Historical case-study fixtures are reconstructed from public facts when their metadata says so.",
        ],
    }


def format_equivalence_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Observational-equivalence report: {report.get('service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Equivalent: `{str(report['equivalent']).lower()}`",
        f"- Questions compared: {summary['questions_compared']}",
        f"- Equivalent questions: {summary['equivalent_questions']}",
        f"- Different questions: {summary['different_questions']}",
        f"- Left events: {summary['left_events']}",
        f"- Right events: {summary['right_events']}",
        "",
        "## Relation",
        "",
        report["model"]["relation"],
        "",
        "## Question comparisons",
        "",
    ]
    if not report["comparisons"]:
        lines.append("No scenarios were selected; the traces are not treated as equivalent.")
    for item in report["comparisons"]:
        lines.extend(
            [
                f"### `{item['id']}`",
                "",
                item["question"],
                "",
                f"- Equivalent: `{str(item['equivalent']).lower()}`",
                f"- Left answerable: `{str(item['left_answerable']).lower()}`",
                f"- Right answerable: `{str(item['right_answerable']).lower()}`",
            ]
        )
        if item["deltas"]:
            lines.append("- Answerability deltas:")
            for delta in item["deltas"]:
                lines.append(f"  - `{delta['requirement']}` {delta['field']}: left `{delta['left']}`, right `{delta['right']}`")
        else:
            lines.append("- Answerability deltas: none")
        lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    return "\n".join(lines)


def _selected_scenarios(contract: dict[str, Any], scenario_ids: list[str] | None) -> list[dict[str, Any]]:
    scenarios = [scenario for scenario in contract.get("scenarios", []) or [] if isinstance(scenario, dict)]
    if not scenario_ids:
        return scenarios
    requested = set(scenario_ids)
    return [scenario for scenario in scenarios if scenario.get("id") in requested]


def _answer_signature(section: dict[str, Any]) -> dict[str, Any]:
    observations = []
    for observation in section.get("minimum_observations", []):
        key = f"{observation.get('signal', '')}:{observation.get('name', '')}"
        required_fields = [str(field) for field in observation.get("fields", [])]
        observed_fields = set(str(field) for field in observation.get("observed_fields", []))
        field_status = {field: field in observed_fields for field in required_fields}
        observations.append(
            {
                "requirement": key,
                "signal_present": bool(observation.get("matching_event_indices")),
                "field_status": field_status,
                "missing_fields": sorted(field for field, present in field_status.items() if not present),
            }
        )
    return {
        "answerable": bool(section.get("answerable")),
        "observations": observations,
    }


def _signature_deltas(left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, str]]:
    deltas: list[dict[str, str]] = []
    if left.get("answerable") != right.get("answerable"):
        deltas.append({"requirement": "$question", "field": "answerable", "left": str(left.get("answerable")).lower(), "right": str(right.get("answerable")).lower()})
    left_obs = {item["requirement"]: item for item in left.get("observations", [])}
    right_obs = {item["requirement"]: item for item in right.get("observations", [])}
    for requirement in sorted(set(left_obs) | set(right_obs)):
        l_item = left_obs.get(requirement, {"signal_present": False, "field_status": {}})
        r_item = right_obs.get(requirement, {"signal_present": False, "field_status": {}})
        if l_item.get("signal_present") != r_item.get("signal_present"):
            deltas.append(
                {
                    "requirement": requirement,
                    "field": "$signal",
                    "left": _present_label(bool(l_item.get("signal_present"))),
                    "right": _present_label(bool(r_item.get("signal_present"))),
                }
            )
        l_fields = l_item.get("field_status", {})
        r_fields = r_item.get("field_status", {})
        for field in sorted(set(l_fields) | set(r_fields)):
            if bool(l_fields.get(field)) != bool(r_fields.get(field)):
                deltas.append(
                    {
                        "requirement": requirement,
                        "field": field,
                        "left": _present_label(bool(l_fields.get(field))),
                        "right": _present_label(bool(r_fields.get(field))),
                    }
                )
    return deltas


def _present_label(value: bool) -> str:
    return "present" if value else "missing"
