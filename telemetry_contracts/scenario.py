from __future__ import annotations

from typing import Any

from .findings import Finding
from .validator import _MISSING, _lookup_field

ADEQUACY_MODEL = {
    "name": "diagnosability-adequacy-v1",
    "relation": (
        "A finite trace is adequate for an incident question when every declared "
        "minimum observation has at least one matching signal and each required "
        "field is present on at least one matching signal instance."
    ),
}


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
    return evaluate_scenario_adequacy(contract, events, scenario)["raw_findings"]


def evaluate_scenario_adequacy(contract: dict[str, Any], events: list[dict[str, Any]], scenario: dict[str, Any] | None) -> dict[str, Any]:
    if scenario is None:
        finding = Finding("error", "scenario.not_found", "no matching scenario was found", "$.scenarios")
        return {
            "model": ADEQUACY_MODEL,
            "id": "",
            "question": "",
            "answerable": False,
            "minimum_observations": [],
            "missing_evidence": [finding.to_dict()],
            "raw_findings": [finding],
        }
    findings: list[Finding] = []
    observations: list[dict[str, Any]] = []
    for index, requirement in enumerate(_minimum_observations(scenario)):
        contract_path = _requirement_contract_path(scenario, index)
        if not isinstance(requirement, dict):
            finding = Finding("error", "scenario.requirement_type", "scenario requirement must be an object", contract_path)
            findings.append(finding)
            observations.append(
                {
                    "index": index,
                    "status": "malformed",
                    "contract_path": contract_path,
                    "missing": [finding.to_dict()],
                }
            )
            continue
        kind = requirement.get("signal") or requirement.get("kind")
        name = requirement.get("name")
        fields = [str(field) for field in requirement.get("fields", []) or []]
        matches = [(event_index, event) for event_index, event in enumerate(events) if event.get("kind") == kind and event.get("name") == name]
        observation = {
            "index": index,
            "signal": kind,
            "name": name,
            "purpose": requirement.get("purpose", ""),
            "fields": fields,
            "contract_path": contract_path,
            "evidence_path": f"events[{kind}={name}]",
            "matching_event_indices": [event_index for event_index, _ in matches],
            "observed_fields": sorted({field for _, event in matches for field in fields if _lookup_field(event, field)[0] is not _MISSING}),
            "missing_fields": [],
            "status": "satisfied",
        }
        if not matches:
            finding = Finding(
                "error",
                "scenario.missing_signal",
                f"scenario '{scenario.get('id')}' requires {kind} '{name}'",
                f"events[{kind}={name}]",
                contract_path=contract_path,
                details={
                    "adequacy_model": ADEQUACY_MODEL["name"],
                    "question": scenario.get("question", ""),
                    "purpose": requirement.get("purpose", ""),
                    "minimum_observation": {"signal": kind, "name": name},
                },
            )
            findings.append(finding)
            observation["status"] = "missing-signal"
            observation["missing"] = [finding.to_dict()]
            observations.append(observation)
            continue
        missing = []
        for field in fields:
            if not any(_lookup_field(event, field)[0] is not _MISSING for _, event in matches):
                missing.append(field)
                findings.append(
                    Finding(
                        "error",
                        "scenario.missing_field",
                        f"scenario '{scenario.get('id')}' cannot answer question without field '{field}' on {kind} '{name}'",
                        f"events[{kind}={name}].{field}",
                        f"{contract_path}.fields",
                        details={
                            "adequacy_model": ADEQUACY_MODEL["name"],
                            "question": scenario.get("question", ""),
                            "purpose": requirement.get("purpose", ""),
                            "minimum_observation": {"signal": kind, "name": name, "field": field},
                            "matching_event_indices": observation["matching_event_indices"],
                        },
                    )
                )
        if missing:
            observation["status"] = "missing-fields"
            observation["missing_fields"] = missing
            observation["missing"] = [finding.to_dict() for finding in findings if finding.contract_path == f"{contract_path}.fields"]
        observations.append(observation)
    return {
        "model": ADEQUACY_MODEL,
        "id": scenario.get("id", ""),
        "question": scenario.get("question", ""),
        "answerable": not any(finding.severity == "error" for finding in findings),
        "minimum_observations": observations,
        "missing_evidence": [finding.to_dict() for finding in findings],
        "raw_findings": findings,
    }


def _minimum_observations(scenario: dict[str, Any]) -> list[Any]:
    observations = scenario.get("minimum_observations")
    if observations is None:
        observations = scenario.get("requires", [])
    return observations if isinstance(observations, list) else []


def _requirement_contract_path(scenario: dict[str, Any], index: int) -> str:
    key = "minimum_observations" if "minimum_observations" in scenario else "requires"
    return f"$.scenarios[{scenario.get('id')}].{key}[{index}]"
