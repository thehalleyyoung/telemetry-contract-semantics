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

import math
from collections import defaultdict, deque
from typing import Any

from .validator import SENSITIVE_FIELD_NAMES, TENANT_IDENTIFIER_FIELD_NAMES, _event_timestamp_ms

_MAX_ALLOWED_VALUES = 8
_CORRELATION_CANDIDATES = ("trace_id", "request_id", "span_id", "correlation_id")
# Temporal ordering is inferred only over workflow-level correlation keys
# (never span_id, which usually identifies a single span, not a workflow).
_SEQUENCE_CORRELATION_KEYS = ("trace_id", "request_id", "correlation_id")
_MAX_SEQUENCE_SIGNALS = 40
_MAX_SEQUENCE_GROUPS = 2000
# Only these kinds are representable as temporal-sequence steps (schema enum);
# never build ordering steps for any other normalized kind (e.g. "event").
_SEQUENCE_KINDS = frozenset({"span", "log", "metric"})


def infer_contract(
    events: list[dict[str, Any]],
    *,
    service: str | None = None,
    infer_ranges: bool = False,
    require_ubiquitous: bool = True,
    infer_sequences: bool = False,
) -> dict[str, Any]:
    """Infer a conservative draft contract from observed telemetry events.

    When ``infer_sequences`` is true, an observed execution order is inferred
    from correlation groups and emitted as a single ``temporal_sequences`` entry
    marked ``required: false`` (a reviewable hypothesis, not an enforced check —
    promote it to ``required: true`` once you trust it).
    """

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

    if infer_sequences:
        order = infer_temporal_order(relevant)
        if order and len(order["steps"]) >= 2:
            sequence: dict[str, Any] = {
                "id": "observed-flow",
                "required": False,
                "group_by": [order["correlation_key"]],
                "steps": order["steps"],
            }
            if order.get("window_ms"):
                sequence["window_ms"] = order["window_ms"]
            contract["temporal_sequences"] = [sequence]

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


def _signal_of(event: dict[str, Any]) -> tuple[str, str] | None:
    kind = event.get("kind")
    name = event.get("name")
    if kind in _SEQUENCE_KINDS and isinstance(name, str) and name:
        return (kind, name)
    return None


def infer_temporal_order(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Infer an observed execution order (a partial order over signals).

    Returns ``None`` unless there is confident, recurring evidence. The result
    contains the chosen workflow correlation key, the confident pairwise
    ``before`` edges, a single linear ``steps`` chain (the longest consistent
    path), and support metadata. Ordering edges are only kept when, in *every*
    group containing both signals (and in at least two such groups), the first
    occurrence of ``a`` strictly precedes the first occurrence of ``b`` — equal
    timestamps are treated as ambiguous, never ordered.
    """

    # Choose the workflow correlation key with the most eligible groups.
    best_key: str | None = None
    best_groups: dict[Any, list[dict[str, Any]]] | None = None
    best_eligible = 1  # require >= 2 eligible groups
    for key in _SEQUENCE_CORRELATION_KEYS:
        groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            value = event.get(key)
            if value in (None, ""):
                continue
            groups[value].append(event)
        eligible = 0
        for group in groups.values():
            signals = {
                _signal_of(event)
                for event in group
                if _event_timestamp_ms(event) is not None and _signal_of(event) is not None
            }
            if len(signals) >= 2:
                eligible += 1
        if eligible > best_eligible:
            best_eligible = eligible
            best_key = key
            best_groups = groups
    if not best_key or best_groups is None:
        return None

    # Per group, record the first observed timestamp of each signal.
    group_first_ts: list[dict[tuple[str, str], float]] = []
    all_signals: set[tuple[str, str]] = set()
    for group in list(best_groups.values())[:_MAX_SEQUENCE_GROUPS]:
        first: dict[tuple[str, str], float] = {}
        for event in group:
            ts = _event_timestamp_ms(event)
            signal = _signal_of(event)
            if ts is None or signal is None:
                continue
            if signal not in first or ts < first[signal]:
                first[signal] = ts
        if first:
            group_first_ts.append(first)
            all_signals.update(first)
    if not (2 <= len(all_signals) <= _MAX_SEQUENCE_SIGNALS):
        return None

    signals = sorted(all_signals)
    edges: dict[tuple[tuple[str, str], tuple[str, str]], int] = {}
    for a in signals:
        for b in signals:
            if a == b:
                continue
            both = [first for first in group_first_ts if a in first and b in first]
            if len(both) >= 2 and all(first[a] < first[b] for first in both):
                edges[(a, b)] = len(both)
    if not edges:
        return None

    path = _longest_path(signals, set(edges))
    if path is None or len(path) < 2:
        return None

    # Support: groups where the whole path is present and strictly ordered.
    support_full = 0
    partial = 0
    max_elapsed = 0.0
    path_set = set(path)
    for first in group_first_ts:
        present = [signal for signal in path if signal in first]
        if not (set(present) & path_set):
            continue
        if len(present) == len(path):
            ordered = all(first[path[i]] < first[path[i + 1]] for i in range(len(path) - 1))
            if ordered:
                support_full += 1
                max_elapsed = max(max_elapsed, first[path[-1]] - first[path[0]])
            else:
                partial += 1
        else:
            partial += 1

    ordering_edges = [
        {
            "before": {"kind": a[0], "name": a[1]},
            "after": {"kind": b[0], "name": b[1]},
            "groups": count,
        }
        for (a, b), count in sorted(edges.items())
    ]
    return {
        "correlation_key": best_key,
        "eligible_groups": best_eligible,
        "steps": [{"kind": kind, "name": name} for kind, name in path],
        "ordering_edges": ordering_edges,
        "support_full_groups": support_full,
        "partial_groups": partial,
        "enforceable": partial == 0 and support_full >= 2,
        "window_ms": int(math.ceil(max_elapsed)) if max_elapsed > 0 else None,
    }


def _longest_path(nodes: list[tuple[str, str]], edges: set[tuple[Any, Any]]) -> list[tuple[str, str]] | None:
    """Deterministic longest path over a DAG; returns ``None`` if cyclic."""

    used_nodes = sorted({node for edge in edges for node in edge})
    adjacency: dict[Any, list[Any]] = defaultdict(list)
    indegree: dict[Any, int] = {node: 0 for node in used_nodes}
    for a, b in edges:
        adjacency[a].append(b)
        indegree[b] += 1

    queue = deque(sorted(node for node in used_nodes if indegree[node] == 0))
    remaining = dict(indegree)
    topo: list[Any] = []
    while queue:
        node = queue.popleft()
        topo.append(node)
        for nxt in sorted(adjacency[node]):
            remaining[nxt] -= 1
            if remaining[nxt] == 0:
                queue.append(nxt)
    if len(topo) != len(used_nodes):
        return None  # cycle: refuse to invent an order

    best_len: dict[Any, int] = {node: 1 for node in used_nodes}
    prev: dict[Any, Any] = {node: None for node in used_nodes}
    for node in topo:
        for nxt in sorted(adjacency[node]):
            candidate = best_len[node] + 1
            if candidate > best_len[nxt]:
                best_len[nxt] = candidate
                prev[nxt] = node
    # End node: longest, tie-broken by smallest node tuple for determinism.
    end = min(used_nodes, key=lambda node: (-best_len[node], node))
    chain: list[Any] = []
    cursor: Any = end
    while cursor is not None:
        chain.append(cursor)
        cursor = prev[cursor]
    chain.reverse()
    return chain
