from __future__ import annotations

from typing import Any

from .findings import Finding
from .validator import _MISSING, _lookup_field


def choose_scenario(contract: dict[str, Any], scenario_id: str | None = None, question: str | None = None) -> dict[str, Any] | None:
    scenarios = contract.get("scenarios") or []
    if scenario_id:
        for scenario in scenarios:
            if isinstance(scenario, dict) and scenario.get("id") == scenario_id:
                return scenario
    if question:
        question_tokens = set(question.lower().replace("?", "").split())
        best: tuple[int, dict[str, Any] | None] = (0, None)
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                continue
            text = f"{scenario.get('question', '')} {scenario.get('id', '')}".lower()
            score = sum(1 for token in question_tokens if token in text)
            if score > best[0]:
                best = (score, scenario)
        return best[1]
    return scenarios[0] if scenarios and isinstance(scenarios[0], dict) else None


def check_scenario(contract: dict[str, Any], events: list[dict[str, Any]], scenario: dict[str, Any] | None) -> list[Finding]:
    if scenario is None:
        return [Finding("error", "scenario.not_found", "no matching scenario was found", "$.scenarios")]
    findings: list[Finding] = []
    for index, requirement in enumerate(scenario.get("requires", []) or []):
        if not isinstance(requirement, dict):
            findings.append(Finding("error", "scenario.requirement_type", "scenario requirement must be an object", f"$.scenarios[{scenario.get('id')}].requires[{index}]"))
            continue
        kind = requirement.get("signal") or requirement.get("kind")
        name = requirement.get("name")
        matches = [event for event in events if event.get("kind") == kind and event.get("name") == name]
        if not matches:
            findings.append(Finding("error", "scenario.missing_signal", f"scenario '{scenario.get('id')}' requires {kind} '{name}'", f"events[{kind}={name}]", f"$.scenarios[{scenario.get('id')}].requires[{index}]"))
            continue
        for field in requirement.get("fields", []) or []:
            if not any(_lookup_field(event, str(field))[0] is not _MISSING for event in matches):
                findings.append(Finding("error", "scenario.missing_field", f"scenario '{scenario.get('id')}' cannot answer question without field '{field}' on {kind} '{name}'", f"events[{kind}={name}].{field}", f"$.scenarios[{scenario.get('id')}].requires[{index}].fields"))
    return findings
