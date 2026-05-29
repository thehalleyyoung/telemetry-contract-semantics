from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any

from .findings import Finding, has_at_least
from .validator import (
    TEMPORAL_PROPERTY_TYPES,
    _event_index,
    _event_matches_step,
    _event_matches_temporal_selector,
    _event_timestamp_ms,
    _normalize_signal_kind,
    _safe_lookup,
    _temporal_message,
    _temporal_property_message,
    _temporal_predicate_path,
    _temporal_predicate_matches,
    _validate_signal,
    validate_contract_shape,
)

MONITOR_MODEL: dict[str, Any] = {
    "name": "bounded-runtime-monitor-v1",
    "judgement": "compile(C) ⇓ M; M ⊢ e₁…eₙ ⇓ R",
    "relation": (
        "A contract compiles to deterministic per-clause monitors. Safety and absence clauses are checked per event; "
        "bounded response and temporal sequences retain only active sliding-window witnesses; ordering and deadline clauses "
        "retain prefix summaries per group; required signal clauses retain matched bits plus per-witness predicate findings."
    ),
    "memory_bound": (
        "O(|signal obligations| + |groups| × |prefix summaries| + active events inside declared windows + findings). "
        "The report includes observed active groups and pending-window witnesses for the concrete run."
    ),
}


def run_compiled_monitor(contract: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    monitor = CompiledMonitor(contract)
    for event in events:
        monitor.ingest(event)
    return monitor.finish()


class CompiledMonitor:
    def __init__(self, contract: dict[str, Any]):
        self.contract = contract
        self.service = contract.get("service")
        self.findings: list[Finding] = validate_contract_shape(contract)
        self.events_seen = 0
        self.relevant_events = 0
        self.signal_states = _compile_signal_states(contract)
        self.sequence_states = _compile_sequence_states(contract)
        self.property_states = _compile_property_states(contract)
        self.max_active_groups = 0
        self.max_pending_responses = 0
        self.max_sequence_buffers = 0

    def ingest(self, event: dict[str, Any]) -> None:
        self.events_seen += 1
        if self.service is not None and event.get("service") not in {self.service, None}:
            return
        self.relevant_events += 1
        self._ingest_signal(event)
        self._ingest_temporal_sequence(event)
        self._ingest_temporal_property(event)
        active_groups = sum(len(item.get("groups", {})) for item in self.sequence_states + self.property_states)
        pending = sum(len(group.get("pending", [])) for item in self.property_states for group in item.get("groups", {}).values())
        sequence_buffers = sum(len(group.get("recent", [])) for item in self.sequence_states for group in item.get("groups", {}).values())
        self.max_active_groups = max(self.max_active_groups, active_groups)
        self.max_pending_responses = max(self.max_pending_responses, pending)
        self.max_sequence_buffers = max(self.max_sequence_buffers, sequence_buffers)

    def finish(self) -> dict[str, Any]:
        for state in self.signal_states:
            if state["required"] and not state["matched"]:
                self.findings.extend(_validate_signal(state["kind"], state["section"], state["index"], state["spec"], [], self.contract))
        for state in self.sequence_states:
            self._finish_sequence(state)
        for state in self.property_states:
            self._finish_property(state)
        finding_dicts = [finding.to_dict() for finding in self.findings]
        return {
            "model": MONITOR_MODEL,
            "service": self.service or "",
            "summary": {
                "pass": not has_at_least(self.findings, "error"),
                "events": self.events_seen,
                "relevant_events": self.relevant_events,
                "findings": len(self.findings),
                "findings_by_code": dict(sorted(Counter(item.code for item in self.findings).items())),
                "compiled_signal_monitors": len(self.signal_states),
                "compiled_temporal_sequence_monitors": len(self.sequence_states),
                "compiled_temporal_property_monitors": len(self.property_states),
                "max_active_groups": self.max_active_groups,
                "max_pending_responses": self.max_pending_responses,
                "max_sequence_buffered_events": self.max_sequence_buffers,
            },
            "compiled_monitors": _compiled_summary(self.signal_states, self.sequence_states, self.property_states),
            "findings": finding_dicts,
        }

    def _ingest_signal(self, event: dict[str, Any]) -> None:
        kind = _normalize_signal_kind(event.get("kind"))
        name = event.get("name")
        for state in self.signal_states:
            if kind == state["kind"] and name == state["name"]:
                state["matched"] = True
                self.findings.extend(_without_missing_signal(_validate_signal(kind, state["section"], state["index"], state["spec"], [event], self.contract)))

    def _ingest_temporal_sequence(self, event: dict[str, Any]) -> None:
        for state in self.sequence_states:
            steps = state["steps"]
            if not any(_event_matches_step(event, step) for step in steps):
                continue
            group_key = _group_key(event, state["group_by"], skip_missing=True)
            if group_key is None:
                continue
            timestamp = _event_timestamp_ms(event)
            if timestamp is None:
                continue
            group = state["groups"].setdefault(group_key, {"progress": 0, "start": None, "last": None, "recent": []})
            window_ms = state.get("window_ms")
            if isinstance(window_ms, (int, float)) and not isinstance(window_ms, bool):
                group["recent"] = [item for item in group["recent"] if timestamp - item["timestamp"] <= float(window_ms)]
            group["recent"].append({"timestamp": timestamp, "name": event.get("name"), "kind": event.get("kind")})
            expected_index = group["progress"]
            if expected_index < len(steps) and _event_matches_step(event, steps[expected_index]):
                if expected_index == 0:
                    group["start"] = timestamp
                group["last"] = timestamp
                group["progress"] = expected_index + 1
                if group["progress"] == len(steps):
                    start = group.get("start")
                    if isinstance(window_ms, (int, float)) and start is not None and timestamp - start > float(window_ms):
                        self.findings.append(Finding("error", "telemetry.temporal_window", _temporal_message(state["sequence"], f"sequence exceeded {window_ms}ms window"), "events", f"{state['path']}.window_ms", details={"group": group_key, "elapsed_ms": timestamp - start}))
                    group["progress"] = 0
                    group["start"] = None
                    group["last"] = None
            elif any(_event_matches_step(event, step) for step in steps[expected_index + 1 :]):
                self.findings.append(Finding("error", "telemetry.temporal_order", _temporal_message(state["sequence"], f"observed later step {event.get('name')!r} before step {expected_index + 1}"), f"event[{_event_index(event)}]", f"{state['path']}.steps[{expected_index}]", _event_index(event), {"group": group_key}))

    def _finish_sequence(self, state: dict[str, Any]) -> None:
        if not state["groups"]:
            self.findings.append(Finding("error", "telemetry.temporal_missing_step", _temporal_message(state["sequence"], "no events matched the required temporal sequence"), "events", state["path"], details={"sequence": state["sequence"].get("id", state["index"])}))
            return
        for group_key, group in state["groups"].items():
            progress = group.get("progress", 0)
            if progress:
                self.findings.append(Finding("error", "telemetry.temporal_missing_step", _temporal_message(state["sequence"], f"missing ordered step {progress + 1} {state['steps'][progress].get('name')!r}"), "events", f"{state['path']}.steps[{progress}]", details={"group": group_key}))

    def _ingest_temporal_property(self, event: dict[str, Any]) -> None:
        for state in self.property_states:
            prop_type = state["type"]
            prop = state["property"]
            path = state["path"]
            if prop_type == "safety":
                selector = prop.get("match")
                condition = prop.get("condition")
                if isinstance(selector, dict) and isinstance(condition, dict) and _event_matches_temporal_selector(event, selector, apply_predicate=False) and not _temporal_predicate_matches(event, condition):
                    self.findings.append(Finding("error", "telemetry.temporal_safety", _temporal_property_message(prop, f"safety condition failed for {event.get('kind')} {event.get('name')!r}"), _temporal_predicate_path(event, condition), f"{path}.condition", _event_index(event), {"property": prop.get("id"), "event": _event_index(event)}))
            elif prop_type == "absence":
                selector = prop.get("forbidden")
                if isinstance(selector, dict) and _event_matches_temporal_selector(event, selector):
                    self.findings.append(Finding("error", "telemetry.temporal_absence", _temporal_property_message(prop, f"forbidden event {event.get('kind')} {event.get('name')!r} was observed"), f"event[{_event_index(event)}]", f"{path}.forbidden", _event_index(event), {"property": prop.get("id")}))
            elif prop_type == "bounded_response":
                self._ingest_response_property(state, event)
            elif prop_type == "ordering":
                self._ingest_ordering_property(state, event)
            elif prop_type == "deadline":
                self._ingest_deadline_property(state, event)

    def _ingest_response_property(self, state: dict[str, Any], event: dict[str, Any]) -> None:
        prop = state["property"]
        trigger = prop.get("trigger")
        response = prop.get("response")
        within_ms = prop.get("within_ms")
        if not isinstance(trigger, dict) or not isinstance(response, dict) or not isinstance(within_ms, (int, float)) or isinstance(within_ms, bool):
            return
        is_trigger = _event_matches_temporal_selector(event, trigger)
        is_response = _event_matches_temporal_selector(event, response)
        if not (is_trigger or is_response):
            return
        timestamp = _event_timestamp_ms(event)
        if timestamp is None:
            return
        group_key = _group_key(event, prop.get("group_by", []), skip_missing=False)
        group = state["groups"].setdefault(group_key, {"pending": []})
        still_pending = []
        for pending in group["pending"]:
            if timestamp > pending["deadline"]:
                self.findings.append(_response_finding(prop, state["path"], pending, group_key))
            else:
                still_pending.append(pending)
        group["pending"] = still_pending
        if is_response:
            group["pending"] = [pending for pending in group["pending"] if not (pending["timestamp"] <= timestamp <= pending["deadline"])]
        if is_trigger:
            group["pending"].append({"timestamp": timestamp, "deadline": timestamp + float(within_ms), "event_index": _event_index(event), "trigger_name": trigger.get("name"), "response_name": response.get("name"), "within_ms": within_ms})

    def _ingest_ordering_property(self, state: dict[str, Any], event: dict[str, Any]) -> None:
        prop = state["property"]
        before = prop.get("before")
        after = prop.get("after")
        if not isinstance(before, dict) or not isinstance(after, dict):
            return
        is_before = _event_matches_temporal_selector(event, before)
        is_after = _event_matches_temporal_selector(event, after)
        if not (is_before or is_after):
            return
        timestamp = _event_timestamp_ms(event)
        if timestamp is None:
            return
        group_key = _group_key(event, prop.get("group_by", []), skip_missing=False)
        group = state["groups"].setdefault(group_key, {"before_times": []})
        if is_before:
            group["before_times"].append(timestamp)
        if is_after:
            allow_equal = prop.get("allow_equal_timestamps", True) is not False
            ordered = any(item <= timestamp if allow_equal else item < timestamp for item in group["before_times"])
            if not ordered:
                self.findings.append(Finding("error", "telemetry.temporal_order", _temporal_property_message(prop, f"{after.get('name')!r} occurred without prior {before.get('name')!r}"), f"event[{_event_index(event)}]", f"{state['path']}.before", _event_index(event), {"property": prop.get("id"), "group": group_key}))

    def _ingest_deadline_property(self, state: dict[str, Any], event: dict[str, Any]) -> None:
        prop = state["property"]
        selector = prop.get("match")
        within_ms = prop.get("within_ms")
        if not isinstance(selector, dict) or not isinstance(within_ms, (int, float)) or isinstance(within_ms, bool):
            return
        start = prop.get("start")
        is_start = isinstance(start, dict) and _event_matches_temporal_selector(event, start)
        is_match = _event_matches_temporal_selector(event, selector)
        if isinstance(start, dict) and not (is_start or is_match):
            return
        timestamp = _event_timestamp_ms(event)
        if timestamp is None:
            return
        group_key = _group_key(event, prop.get("group_by", []), skip_missing=False)
        group = state["groups"].setdefault(group_key, {"base": None})
        if isinstance(start, dict):
            if is_start and (group["base"] is None or timestamp < group["base"]):
                group["base"] = timestamp
        elif group["base"] is None or timestamp < group["base"]:
            group["base"] = timestamp
        if is_match and group["base"] is not None and timestamp - group["base"] > float(within_ms):
            self.findings.append(Finding("error", "telemetry.temporal_deadline", _temporal_property_message(prop, f"{selector.get('name')!r} missed {within_ms}ms deadline by {timestamp - group['base'] - float(within_ms):.3f}ms"), f"event[{_event_index(event)}]", f"{state['path']}.within_ms", _event_index(event), {"property": prop.get("id"), "group": group_key, "elapsed_ms": timestamp - group["base"]}))

    def _finish_property(self, state: dict[str, Any]) -> None:
        if state["type"] != "bounded_response":
            return
        for group_key, group in state["groups"].items():
            for pending in group.get("pending", []):
                self.findings.append(_response_finding(state["property"], state["path"], pending, group_key))


def _compile_signal_states(contract: dict[str, Any]) -> list[dict[str, Any]]:
    states = []
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        raw = contract.get(section, []) or []
        if not isinstance(raw, list):
            continue
        for index, spec in enumerate(raw):
            if isinstance(spec, dict) and isinstance(spec.get("name"), str) and spec.get("name"):
                states.append({"section": section, "kind": kind, "index": index, "name": spec["name"], "required": spec.get("required", True), "matched": False, "spec": spec})
    return states


def _compile_sequence_states(contract: dict[str, Any]) -> list[dict[str, Any]]:
    states = []
    raw = contract.get("temporal_sequences", []) or []
    if not isinstance(raw, list):
        return states
    for index, sequence in enumerate(raw):
        if not isinstance(sequence, dict) or sequence.get("required", True) is False:
            continue
        steps = sequence.get("steps")
        if isinstance(steps, list) and steps and all(isinstance(step, dict) for step in steps):
            states.append({"index": index, "sequence": sequence, "steps": steps, "group_by": sequence.get("group_by", []), "window_ms": sequence.get("window_ms"), "path": f"$.temporal_sequences[{index}]", "groups": {}})
    return states


def _compile_property_states(contract: dict[str, Any]) -> list[dict[str, Any]]:
    states = []
    raw = contract.get("temporal_properties", []) or []
    if not isinstance(raw, list):
        return states
    for index, prop in enumerate(raw):
        if isinstance(prop, dict) and prop.get("required", True) is not False and prop.get("type") in TEMPORAL_PROPERTY_TYPES:
            states.append({"index": index, "property": prop, "type": prop["type"], "path": f"$.temporal_properties[{index}]", "groups": {}})
    return states


def _without_missing_signal(findings: list[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.code != "telemetry.missing_signal"]


def _group_key(event: dict[str, Any], raw_keys: Any, *, skip_missing: bool) -> tuple[Any, ...] | None:
    keys = raw_keys if isinstance(raw_keys, list) and all(isinstance(item, str) for item in raw_keys) else []
    if not keys:
        return ("__all__",)
    values = []
    for key in keys:
        value = _safe_lookup(event, key)
        if value is None:
            if skip_missing:
                return None
            value = f"__missing__:{key}:event[{_event_index(event)}]"
        values.append(value)
    return tuple(values)


def _response_finding(prop: dict[str, Any], path: str, pending: dict[str, Any], group_key: tuple[Any, ...]) -> Finding:
    return Finding(
        "error",
        "telemetry.temporal_response",
        _temporal_property_message(prop, f"no response {pending['response_name']!r} within {pending['within_ms']}ms after trigger {pending['trigger_name']!r}"),
        f"event[{pending['event_index']}]",
        f"{path}.response",
        pending["event_index"],
        {"property": prop.get("id"), "group": group_key, "within_ms": pending["within_ms"]},
    )


def _compiled_summary(signals: list[dict[str, Any]], sequences: list[dict[str, Any]], properties: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "signals": [{"kind": item["kind"], "name": item["name"], "required": item["required"]} for item in signals],
        "temporal_sequences": [{"id": item["sequence"].get("id", item["index"]), "steps": len(item["steps"]), "window_ms": item.get("window_ms")} for item in sequences],
        "temporal_properties": [{"id": item["property"].get("id", item["index"]), "type": item["type"], "group_by": item["property"].get("group_by", [])} for item in properties],
    }


def format_monitor_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Runtime monitor report: {report.get('service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Judgement: `{report['model']['judgement']}`",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Events: {summary['events']} input / {summary['relevant_events']} service-relevant",
        f"- Findings: {summary['findings']}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        f"- Compiled monitors: {summary['compiled_signal_monitors']} signal, {summary['compiled_temporal_sequence_monitors']} sequence, {summary['compiled_temporal_property_monitors']} temporal-property",
        f"- Observed memory envelope: {summary['max_active_groups']} active groups, {summary['max_pending_responses']} pending responses, {summary['max_sequence_buffered_events']} sequence-window events",
        "",
        "## Semantics and memory bound",
        "",
        report["model"]["relation"],
        "",
        report["model"]["memory_bound"],
        "",
        "## Findings",
        "",
    ]
    if not report.get("findings"):
        lines.append("No findings.")
    else:
        for finding in report["findings"]:
            lines.append(f"- **{finding['severity']} `{finding['code']}`** ({finding.get('formal_clause', 'unclassified')}): {finding['message']}")
    return "\n".join(lines).rstrip()
