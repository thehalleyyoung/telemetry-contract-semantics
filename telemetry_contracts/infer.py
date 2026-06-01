"""Draft-contract inference.

Instead of asking you to author a contract before you get value, this module
reads the telemetry you already have and writes a conservative, lint-clean
*draft* contract you can review and tighten. It flips the onboarding story from
"write a contract first" to "here is a contract derived from your data; edit it."

The inference is intentionally conservative to stay useful on the *next* batch
of telemetry too:

* A field is only marked ``required`` when it is present on every observed
  occurrence of that signal.
* ``allowed_values`` is only emitted for low-cardinality, fully-string fields.
* Numeric ``min``/``max`` bounds are not inferred by default (observed extremes
  make brittle contracts); pass ``infer_ranges=True`` to opt in.
* Fields whose names look sensitive are classified so the draft does not trip
  the unclassified-sensitive-field lint.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .validator import SENSITIVE_FIELD_NAMES, TENANT_IDENTIFIER_FIELD_NAMES

_MAX_ALLOWED_VALUES = 8
_CORRELATION_CANDIDATES = ("trace_id", "request_id", "span_id", "correlation_id")


def infer_contract(
    events: list[dict[str, Any]],
    *,
    service: str | None = None,
    infer_ranges: bool = False,
    require_ubiquitous: bool = True,
) -> dict[str, Any]:
    """Infer a conservative draft contract from observed telemetry events."""

    chosen_service = service or _dominant_service(events) or "service"
    relevant = [event for event in events if event.get("service") in {chosen_service, None}]

    signals: dict[str, dict[tuple[str, str], _SignalAcc]] = {"span": {}, "metric": {}, "log": {}}
    for event in relevant:
        kind = str(event.get("kind", "event"))
        if kind not in signals:
            continue
        name = event.get("name")
        if not isinstance(name, str) or not name:
            continue
        acc = signals[kind].setdefault((kind, name), _SignalAcc(name))
        acc.observe(event)

    contract: dict[str, Any] = {
        "version": "1.0",
        "service": chosen_service,
        "metadata": {
            "owner": "TODO-owner",
            "inferred": {
                "generated_by": "telemetry-contracts infer-contract",
                "sample_events": len(relevant),
                "status": "draft - review before enforcing",
            },
        },
    }

    spans = [acc.to_signal(infer_ranges, require_ubiquitous) for acc in _ordered(signals["span"])]
    metrics = [acc.to_signal(infer_ranges, require_ubiquitous, metric=True) for acc in _ordered(signals["metric"])]
    logs = [acc.to_signal(infer_ranges, require_ubiquitous, log=True) for acc in _ordered(signals["log"])]
    if spans:
        contract["spans"] = spans
    if metrics:
        contract["metrics"] = metrics
    if logs:
        contract["logs"] = logs

    correlation_keys = _observed_correlation_keys(relevant)
    if correlation_keys:
        require_on = [section for section in ("spans", "metrics", "logs") if contract.get(section)]
        contract["correlation"] = {"keys": correlation_keys, "require_on": require_on}

    static_expectations = {
        section: sorted({signal["name"] for signal in contract.get(section, [])})
        for section in ("spans", "metrics", "logs")
        if contract.get(section)
    }
    if static_expectations:
        contract["static_expectations"] = static_expectations

    return contract


class _SignalAcc:
    def __init__(self, name: str) -> None:
        self.name = name
        self.count = 0
        self.field_count: dict[str, int] = defaultdict(int)
        self.field_types: dict[str, set[str]] = defaultdict(set)
        self.field_values: dict[str, set[Any]] = defaultdict(set)
        self.field_values_capped: dict[str, bool] = defaultdict(bool)
        self.field_min: dict[str, float] = {}
        self.field_max: dict[str, float] = {}

    def observe(self, event: dict[str, Any]) -> None:
        self.count += 1
        for key, value in _fields(event).items():
            self.field_count[key] += 1
            self.field_types[key].add(_json_type(value))
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                self.field_min[key] = min(self.field_min.get(key, value), value)
                self.field_max[key] = max(self.field_max.get(key, value), value)
            if isinstance(value, str):
                if len(self.field_values[key]) <= _MAX_ALLOWED_VALUES:
                    self.field_values[key].add(value)
                else:
                    self.field_values_capped[key] = True

    def to_signal(self, infer_ranges: bool, require_ubiquitous: bool, *, metric: bool = False, log: bool = False) -> dict[str, Any]:
        signal: dict[str, Any] = {"name": self.name, "required": True}
        fields: dict[str, Any] = {}
        for field_name in sorted(self.field_count):
            if field_name == "value" and metric:
                continue
            fields[field_name] = self._field_spec(field_name, infer_ranges, require_ubiquitous)
        if fields:
            signal["fields"] = fields
        if metric and "value" in self.field_count:
            signal["value"] = self._field_spec("value", infer_ranges, require_ubiquitous=False, drop_required=True)
        return signal

    def _field_spec(self, field_name: str, infer_ranges: bool, require_ubiquitous: bool, *, drop_required: bool = False) -> dict[str, Any]:
        spec: dict[str, Any] = {}
        types = self.field_types.get(field_name, set())
        if len(types) == 1:
            spec["type"] = next(iter(types))
        if not drop_required:
            ubiquitous = self.field_count[field_name] == self.count
            spec["required"] = bool(ubiquitous) if require_ubiquitous else False
        values = self.field_values.get(field_name, set())
        if (
            types == {"string"}
            and not self.field_values_capped.get(field_name)
            and 1 < len(values) <= _MAX_ALLOWED_VALUES
            and not _looks_identifier(field_name)
        ):
            spec["allowed_values"] = sorted(values)
        if infer_ranges and field_name in self.field_min and types <= {"integer", "number"}:
            spec["min"] = self.field_min[field_name]
            spec["max"] = self.field_max[field_name]
        if SENSITIVE_FIELD_NAMES.search(field_name) or TENANT_IDENTIFIER_FIELD_NAMES.search(field_name):
            spec["sensitivity"] = "sensitive"
            spec.setdefault("transformation", "raw")
        return spec


def _ordered(signal_map: dict[tuple[str, str], _SignalAcc]) -> list[_SignalAcc]:
    return [signal_map[key] for key in sorted(signal_map)]


def _fields(event: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for container in ("attributes", "tags", "fields"):
        values = event.get(container)
        if isinstance(values, dict):
            for key, value in values.items():
                fields.setdefault(str(key), value)
    if "value" in event and event.get("kind") == "metric":
        fields.setdefault("value", event["value"])
    return fields


def _dominant_service(events: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = defaultdict(int)
    for event in events:
        service = event.get("service")
        if isinstance(service, str) and service:
            counts[service] += 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _observed_correlation_keys(events: list[dict[str, Any]]) -> list[str]:
    present: set[str] = set()
    for event in events:
        for key in _CORRELATION_CANDIDATES:
            if event.get(key) not in (None, ""):
                present.add(key)
    return [key for key in _CORRELATION_CANDIDATES if key in present]


def _looks_identifier(field_name: str) -> bool:
    lowered = field_name.lower()
    return lowered.endswith("_id") or lowered.endswith("id") or "uuid" in lowered or "guid" in lowered


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "null"
