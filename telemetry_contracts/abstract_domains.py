from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

SEVERITY_ORDER = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]


def _attrs(event: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("attributes", "tags", "fields"):
        if isinstance(event.get(key), dict):
            out.update(event[key])
    return out


def _event_key(event: dict[str, Any]) -> tuple[str, str]:
    return (str(event.get("kind", "unknown")), str(event.get("name", "unknown")))


@dataclass(frozen=True)
class DomainSummary:
    name: str
    values: dict[str, Any]
    join: str
    widening: str
    limitations: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "values": self.values,
            "join": self.join,
            "widening": self.widening,
            "limitations": self.limitations,
        }


def summarize_abstract_domains(contract: dict[str, Any], events: list[dict[str, Any]] | None = None, *, string_bound: int = 5) -> dict[str, Any]:
    """Prototype abstract domains used by static/runtime telemetry reasoning.

    The summary is intentionally finite and deterministic: joins union observed or
    declared evidence until a bounded top element is reached; widening collapses
    growing sets to `many`/`top` rather than retaining unbounded production values.
    """
    events = events or []
    domains = [
        _bounded_strings(contract, events, string_bound),
        _attribute_presence(contract, events),
        _severity(contract, events),
        _units(contract, events),
        _privacy(contract, events),
        _path_feasibility(contract, events),
    ]
    return {
        "summary": {
            "domains": len(domains),
            "events": len(events),
            "string_bound": string_bound,
            "signals": sorted({f"{kind}:{name}" for kind, name in [_event_key(e) for e in events]}),
        },
        "domains": [domain.to_dict() for domain in domains],
    }


def _bounded_strings(contract: dict[str, Any], events: list[dict[str, Any]], bound: int) -> DomainSummary:
    values: dict[str, set[str]] = {}
    for event in events:
        key = ":".join(_event_key(event))
        for field, value in _attrs(event).items():
            if isinstance(value, str):
                values.setdefault(f"{key}.{field}", set()).add(value)
    compact = {key: (sorted(vals) if len(vals) <= bound else {"state": "many", "examples": sorted(vals)[:bound], "distinct": len(vals)}) for key, vals in sorted(values.items())}
    return DomainSummary(
        "bounded_strings",
        compact,
        "set union while cardinality <= bound; otherwise many",
        "collapse to many after the configured bound",
        "tracks exact finite fixture strings only, not all production values",
    )


def _attribute_presence(contract: dict[str, Any], events: list[dict[str, Any]]) -> DomainSummary:
    declared: dict[str, set[str]] = {}
    observed: dict[str, set[str]] = {}
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for spec in contract.get(section, []) or []:
            if isinstance(spec, dict) and isinstance(spec.get("name"), str):
                key = f"{kind}:{spec['name']}"
                fields = set()
                for container in ("fields", "attributes", "tags"):
                    if isinstance(spec.get(container), dict):
                        fields.update(str(item) for item in spec[container])
                declared[key] = fields
    for event in events:
        observed.setdefault(":".join(_event_key(event)), set()).update(_attrs(event))
    values = {}
    for key in sorted(set(declared) | set(observed)):
        req = declared.get(key, set())
        obs = observed.get(key, set())
        values[key] = {
            "must": sorted(req & obs),
            "may": sorted((req | obs) - (req & obs)),
            "missing_declared": sorted(req - obs),
            "observed_extra": sorted(obs - req),
        }
    return DomainSummary("attribute_presence", values, "must=intersection, may=union", "drop per-event provenance and keep field sets", "presence is fixture-relative and path-insensitive unless paired with path_feasibility")


def _severity(contract: dict[str, Any], events: list[dict[str, Any]]) -> DomainSummary:
    by_log: dict[str, set[str]] = {}
    for event in events:
        if event.get("kind") == "log" and event.get("severity"):
            by_log.setdefault(str(event.get("name")), set()).add(str(event.get("severity")).upper())
    values = {name: {"observed": sorted(vals), "join": _max_severity(vals)} for name, vals in sorted(by_log.items())}
    return DomainSummary("severity", values, "maximum severity by operational order", "collapse unknown labels to top=FATAL", "custom backend severity scales are normalized to common labels only")


def _max_severity(values: set[str]) -> str:
    ranks = {name: index for index, name in enumerate(SEVERITY_ORDER)}
    return max(values, key=lambda item: ranks.get(item, len(SEVERITY_ORDER))) if values else "bottom"


def _units(contract: dict[str, Any], events: list[dict[str, Any]]) -> DomainSummary:
    values: dict[str, set[str]] = {}
    for spec in contract.get("metrics", []) or []:
        if isinstance(spec, dict) and spec.get("name") and spec.get("unit"):
            values.setdefault(str(spec["name"]), set()).add(str(spec["unit"]))
    for event in events:
        if event.get("kind") == "metric" and event.get("unit"):
            values.setdefault(str(event.get("name")), set()).add(str(event["unit"]))
    return DomainSummary("units", {k: sorted(v) for k, v in sorted(values.items())}, "equal units stay exact; conflicts join to unit-set", "collapse incompatible growing unit sets to mixed", "does not perform physical dimensional analysis beyond declared strings")


def _privacy(contract: dict[str, Any], events: list[dict[str, Any]]) -> DomainSummary:
    values: dict[str, set[str]] = {}
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for spec in contract.get(section, []) or []:
            if not isinstance(spec, dict) or not isinstance(spec.get("name"), str):
                continue
            for container in ("fields", "attributes", "tags"):
                raw = spec.get(container, {}) or {}
                if isinstance(raw, dict):
                    for field, field_spec in raw.items():
                        if isinstance(field_spec, dict):
                            cls = field_spec.get("classification") or field_spec.get("privacy") or field_spec.get("sensitivity")
                            if cls:
                                values.setdefault(f"{kind}:{spec['name']}.{field}", set()).add(str(cls))
    return DomainSummary("privacy_class", {k: sorted(v) for k, v in sorted(values.items())}, "least upper bound is the most restrictive class present", "unknown or conflicting classes widen to sensitive", "classification depends on explicit contract annotations")


def _path_feasibility(contract: dict[str, Any], events: list[dict[str, Any]]) -> DomainSummary:
    branches: dict[str, dict[str, Any]] = {}
    observed_by_signal: dict[str, list[dict[str, Any]]] = {}
    for event_index, event in enumerate(events, start=1):
        event_with_index = dict(event)
        event_with_index.setdefault("_index", event_index)
        observed_by_signal.setdefault(":".join(_event_key(event)), []).append(event_with_index)
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for spec in contract.get(section, []) or []:
            if not isinstance(spec, dict) or not isinstance(spec.get("name"), str):
                continue
            signal = f"{kind}:{spec['name']}"
            for index, req in enumerate(spec.get("conditional_requirements", []) or []):
                if not isinstance(req, dict):
                    continue
                condition = req.get("if", {})
                matches = [event for event in observed_by_signal.get(signal, []) if _condition_matches(condition, event)]
                branches[f"{signal}.conditional[{index}]"] = {
                    "condition": condition,
                    "state": "feasible" if matches else "unknown",
                    "witness_events": [event.get("_index") for event in matches[:5]],
                }
    return DomainSummary("path_feasibility", branches, "feasible dominates unknown; infeasible only when explicitly contradicted", "merge loop/retry paths by condition id and bounded witnesses", "prototype is condition-sensitive but not a full control-flow analyzer")


def _condition_matches(condition: Any, event: dict[str, Any]) -> bool:
    if not isinstance(condition, dict) or not isinstance(condition.get("field"), str):
        return False
    attrs = _attrs(event)
    field = condition["field"]
    present = field in attrs or field in event
    value = attrs.get(field, event.get(field))
    if "present" in condition and condition["present"] is not present:
        return False
    if "equals" in condition:
        return present and value == condition["equals"]
    if isinstance(condition.get("allowed_values"), list):
        return present and value in condition["allowed_values"]
    return present


def format_abstract_domains_markdown(report: dict[str, Any]) -> str:
    lines = ["# Abstract telemetry domains", "", f"- Domains: {report['summary']['domains']}", f"- Events: {report['summary']['events']}", f"- String bound: {report['summary']['string_bound']}", ""]
    for domain in report["domains"]:
        lines.extend([f"## {domain['name']}", "", f"- Join: {domain['join']}", f"- Widening: {domain['widening']}", f"- Limitations: {domain['limitations']}", "", "```json", json.dumps(domain['values'], indent=2, sort_keys=True), "```", ""])
    return "\n".join(lines)
