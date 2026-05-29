from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

OBSERVATION_DOMAIN: list[dict[str, Any]] = [
    {
        "object": "span",
        "meaning": "An operation interval in a finite trace event structure.",
        "jsonl_fields": ["kind=span", "service", "name", "trace_id", "span_id", "parent_span_id", "attributes", "timestamp_ms", "start_time_unix_nano", "end_time_unix_nano"],
        "otlp_fields": ["resourceSpans[].resource.attributes", "scopeSpans[].spans[].name", "traceId", "spanId", "parentSpanId", "attributes", "startTimeUnixNano", "endTimeUnixNano", "status", "events", "links"],
        "checker_use": "presence, field predicates, correlation keys, temporal ordering, and scenario evidence",
    },
    {
        "object": "log",
        "meaning": "A timestamped diagnostic record that may attach to a trace/span.",
        "jsonl_fields": ["kind=log", "service", "name", "severity", "message", "trace_id", "span_id", "fields", "timestamp_ms", "time_unix_nano"],
        "otlp_fields": ["resourceLogs[].resource.attributes", "scopeLogs[].logRecords[].body", "severityText", "traceId", "spanId", "attributes", "timeUnixNano", "observedTimeUnixNano"],
        "checker_use": "severity/message policies, field predicates, privacy checks, correlation, and incident-question evidence",
    },
    {
        "object": "metric",
        "meaning": "A measurement point or aggregate over a finite window.",
        "jsonl_fields": ["kind=metric", "service", "name", "value", "tags", "metric_type", "aggregation_temporality", "is_monotonic", "time_unix_nano"],
        "otlp_fields": ["resourceMetrics[].resource.attributes", "scopeMetrics[].metrics[].name", "sum", "gauge", "histogram", "exponentialHistogram", "summary", "dataPoints[].attributes", "aggregationTemporality", "isMonotonic"],
        "checker_use": "metric presence, value bounds, units, cardinality, temporality metadata, and scenario evidence",
    },
    {
        "object": "resource",
        "meaning": "Entity metadata shared by spans, logs, or metrics, including service identity.",
        "jsonl_fields": ["service", "attributes.service.name", "fields.service.name", "tags.service.name"],
        "otlp_fields": ["resource.attributes", "resource.droppedAttributesCount"],
        "checker_use": "service scoping, ownership, common fields, and provenance of imported evidence",
    },
    {
        "object": "scope",
        "meaning": "Instrumentation library or scope that produced observations.",
        "jsonl_fields": ["scope", "instrumentation_scope", "instrumentation_library"],
        "otlp_fields": ["scopeSpans[].scope", "scopeMetrics[].scope", "scopeLogs[].scope", "instrumentationLibrarySpans[]", "instrumentationLibraryMetrics[]", "instrumentationLibraryLogs[]"],
        "checker_use": "import audit context and future static/runtime alignment",
    },
    {
        "object": "exemplar",
        "meaning": "Metric sample that can point back to a trace/span witness.",
        "jsonl_fields": ["exemplars", "trace_id", "span_id"],
        "otlp_fields": ["dataPoints[].exemplars[].traceId", "dataPoints[].exemplars[].spanId", "dataPoints[].exemplars[].filteredAttributes"],
        "checker_use": "future cross-signal causality between sampled metrics and traces",
    },
    {
        "object": "timestamp",
        "meaning": "Ordering evidence used to build happens-before checks over finite traces.",
        "jsonl_fields": ["timestamp_ms", "time_ms", "start_time_ms", "end_time_ms", "timestamp", "time", "time_unix_nano", "start_time_unix_nano", "end_time_unix_nano"],
        "otlp_fields": ["startTimeUnixNano", "endTimeUnixNano", "timeUnixNano", "observedTimeUnixNano"],
        "checker_use": "temporal sequence ordering, incident-window grouping, and deadline/window diagnostics",
    },
    {
        "object": "attribute",
        "meaning": "A named value attached to spans, logs, metrics, resources, or exemplars.",
        "jsonl_fields": ["attributes", "fields", "tags", "value"],
        "otlp_fields": ["attributes[].key", "attributes[].value", "filteredAttributes", "body"],
        "checker_use": "required fields, primitive types, allowed values, regexes, numeric bounds, units, transformations, privacy, and cardinality",
    },
    {
        "object": "provenance",
        "meaning": "Evidence about where an observation came from and how it was normalized.",
        "jsonl_fields": ["_line", "source", "source_path", "normalization", "import_warnings"],
        "otlp_fields": ["resource/scope array indexes", "source JSON path", "droppedAttributesCount", "schemaUrl"],
        "checker_use": "bounded claims, reproducibility, skipped-record diagnostics, and auditability of imported collector evidence",
    },
]

SATISFACTION_RELATION = {
    "notation": "T ⊨ C",
    "definition": "A finite telemetry trace T satisfies contract C when every well-formed contract obligation evaluates to true over the observations relevant to C.service under declared assumptions.",
    "states": {
        "present": "A required observation or field exists and all predicates hold.",
        "absent": "A required signal or field has no witness in T.",
        "malformed": "The contract or evidence cannot be interpreted by the declared domain.",
        "partial": "Some evidence exists but required predicates, correlation, ordering, or scenario fields fail.",
        "unknown": "The artifact lacks enough modeled evidence to prove the obligation either way; current checker reports this as missing evidence when the contract requires it.",
        "transformed": "Evidence is accepted only when its declared transformation is allowed by the privacy/diagnosability policy for that field.",
    },
}


def describe_model(events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "observation_domain": OBSERVATION_DOMAIN,
        "satisfaction_relation": SATISFACTION_RELATION,
    }
    if events is not None:
        report["observed_artifact"] = summarize_events(events)
        report["event_structure"] = build_event_structure(events)
    return report


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts_by_kind = Counter(str(event.get("kind", "unknown")) for event in events)
    names_by_kind: dict[str, set[str]] = defaultdict(set)
    fields_by_kind: dict[str, set[str]] = defaultdict(set)
    correlation_keys = Counter()
    timestamp_fields = Counter()
    for event in events:
        kind = str(event.get("kind", "unknown"))
        if event.get("name") is not None:
            names_by_kind[kind].add(str(event["name"]))
        for container in ("attributes", "fields", "tags"):
            raw = event.get(container)
            if isinstance(raw, dict):
                fields_by_kind[kind].update(str(key) for key in raw)
        for key in ("trace_id", "span_id", "request_id", "correlation_id"):
            if event.get(key) not in (None, ""):
                correlation_keys[key] += 1
        for key in ("timestamp_ms", "time_ms", "start_time_ms", "end_time_ms", "timestamp", "time", "time_unix_nano", "start_time_unix_nano", "end_time_unix_nano"):
            if key in event:
                timestamp_fields[key] += 1
    return {
        "event_count": len(events),
        "counts_by_kind": dict(sorted(counts_by_kind.items())),
        "names_by_kind": {kind: sorted(names) for kind, names in sorted(names_by_kind.items())},
        "fields_by_kind": {kind: sorted(fields) for kind, fields in sorted(fields_by_kind.items())},
        "correlation_key_counts": dict(sorted(correlation_keys.items())),
        "timestamp_field_counts": dict(sorted(timestamp_fields.items())),
    }


def build_event_structure(events: list[dict[str, Any]], group_by: list[str] | None = None) -> dict[str, Any]:
    """Build the finite event-structure view used by reports and model output."""
    nodes = [_event_node(index, event) for index, event in enumerate(events)]
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    span_by_identity = {
        (node.get("trace_id"), node.get("span_id")): node
        for node in nodes
        if node["kind"] == "span" and node.get("trace_id") and node.get("span_id")
    }
    span_by_id = {
        node["span_id"]: node
        for node in nodes
        if node["kind"] == "span" and node.get("span_id")
    }

    def add_edge(source: dict[str, Any] | None, target: dict[str, Any] | None, relation: str, evidence: str) -> None:
        if not source or not target or source["id"] == target["id"]:
            return
        key = (source["id"], target["id"], relation)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"from": source["id"], "to": target["id"], "relation": relation, "evidence": evidence})

    for node in nodes:
        event = events[node["index"]]
        if node["kind"] == "span" and node.get("parent_span_id"):
            parent = span_by_identity.get((node.get("trace_id"), node.get("parent_span_id"))) or span_by_id.get(node["parent_span_id"])
            add_edge(parent, node, "parent-child", "parent_span_id")
        if node["kind"] == "span":
            for link in event.get("links", []) or []:
                if not isinstance(link, dict):
                    continue
                linked = span_by_identity.get((link.get("trace_id", link.get("traceId", node.get("trace_id"))), link.get("span_id", link.get("spanId"))))
                add_edge(linked, node, "span-link", "links[]")
        if node["kind"] == "log":
            attached = span_by_identity.get((node.get("trace_id"), node.get("span_id"))) or span_by_id.get(node.get("span_id"))
            add_edge(attached, node, "log-attachment", "trace_id/span_id")
        if node["kind"] == "metric":
            for exemplar in event.get("exemplars", []) or []:
                if not isinstance(exemplar, dict):
                    continue
                span = span_by_identity.get((exemplar.get("trace_id", exemplar.get("traceId", node.get("trace_id"))), exemplar.get("span_id", exemplar.get("spanId"))))
                add_edge(span, node, "metric-exemplar", "exemplars[]")

    windows = _incident_windows(nodes, group_by)
    for window in windows:
        timed = [node for node in window["nodes"] if node.get("timestamp_ms") is not None]
        timed.sort(key=lambda node: (node["timestamp_ms"], node["index"]))
        for before, after in zip(timed, timed[1:]):
            before_end = before.get("end_timestamp_ms") if before.get("end_timestamp_ms") is not None else before["timestamp_ms"]
            if before_end <= after["timestamp_ms"]:
                add_edge(before, after, "happens-before", "timestamp order")

    concurrency = _concurrent_span_pairs(nodes, seen_edges)
    diagrams = [_format_window_diagram(window, edges, concurrency) for window in windows[:10]]
    return {
        "model": "finite-event-structure",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "concurrency_pair_count": len(concurrency),
        "nodes": nodes,
        "edges": sorted(edges, key=lambda edge: (edge["from"], edge["to"], edge["relation"])),
        "concurrency": concurrency,
        "incident_windows": [
            {
                "id": window["id"],
                "group": window["group"],
                "node_ids": [node["id"] for node in window["nodes"]],
                "start_ms": window["start_ms"],
                "end_ms": window["end_ms"],
            }
            for window in windows
        ],
        "diagrams": diagrams,
    }


def format_event_structure_markdown(event_structure: dict[str, Any]) -> str:
    lines = [
        "## Incident-window event-structure diagrams",
        "",
        f"- Nodes: {event_structure['node_count']}",
        f"- Causal/happens-before edges: {event_structure['edge_count']}",
        f"- Concurrent span pairs: {event_structure['concurrency_pair_count']}",
        "",
    ]
    diagrams = event_structure.get("diagrams") or []
    if not diagrams:
        lines.append("No observations were available to diagram.")
        return "\n".join(lines)
    for diagram in diagrams:
        lines.extend([f"### {diagram['title']}", "", "```mermaid", diagram["mermaid"], "```", ""])
    return "\n".join(lines).rstrip()


def format_model_markdown(report: dict[str, Any]) -> str:
    lines = ["# Telemetry Contracts Observation Model", "", f"Satisfaction: `{report['satisfaction_relation']['notation']}` — {report['satisfaction_relation']['definition']}", "", "## Observation domain", ""]
    lines.append("| Object | Meaning | JSONL fields | OTLP fields | Checker use |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in report["observation_domain"]:
        lines.append(
            "| {object} | {meaning} | `{jsonl}` | `{otlp}` | {checker_use} |".format(
                object=item["object"],
                meaning=item["meaning"],
                jsonl="`, `".join(item["jsonl_fields"]),
                otlp="`, `".join(item["otlp_fields"]),
                checker_use=item["checker_use"],
            )
        )
    lines.extend(["", "## Satisfaction states", ""])
    for state, meaning in report["satisfaction_relation"]["states"].items():
        lines.append(f"- **{state}:** {meaning}")
    observed = report.get("observed_artifact")
    if isinstance(observed, dict):
        lines.extend(["", "## Observed artifact summary", "", f"- Events: {observed['event_count']}"])
        lines.append(f"- Counts by kind: `{observed['counts_by_kind']}`")
        lines.append(f"- Names by kind: `{observed['names_by_kind']}`")
        lines.append(f"- Fields by kind: `{observed['fields_by_kind']}`")
        lines.append(f"- Correlation key counts: `{observed['correlation_key_counts']}`")
        lines.append(f"- Timestamp field counts: `{observed['timestamp_field_counts']}`")
    event_structure = report.get("event_structure")
    if isinstance(event_structure, dict):
        lines.extend(["", format_event_structure_markdown(event_structure)])
    return "\n".join(lines)


def _event_node(index: int, event: dict[str, Any]) -> dict[str, Any]:
    timestamp_ms = _event_timestamp_ms(event)
    end_timestamp_ms = _event_end_timestamp_ms(event)
    span_id = _lookup_any(event, "span_id", "spanId")
    trace_id = _lookup_any(event, "trace_id", "traceId")
    return {
        "id": f"e{index}",
        "index": index,
        "kind": str(event.get("kind", "unknown")),
        "name": str(event.get("name", event.get("message", f"event-{index}"))),
        "service": event.get("service"),
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": _lookup_any(event, "parent_span_id", "parentSpanId"),
        "request_id": _lookup_any(event, "request_id", "requestId"),
        "correlation_id": _lookup_any(event, "correlation_id", "correlationId"),
        "timestamp_ms": timestamp_ms,
        "end_timestamp_ms": end_timestamp_ms,
        "label": _node_label(event),
    }


def _node_label(event: dict[str, Any]) -> str:
    kind = str(event.get("kind", "unknown"))
    name = str(event.get("name", event.get("message", "event")))
    return f"{kind}:{name}"


def _incident_windows(nodes: list[dict[str, Any]], group_by: list[str] | None) -> list[dict[str, Any]]:
    keys = group_by or ["trace_id", "request_id", "correlation_id"]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        values = tuple(node.get(key) for key in keys if node.get(key) not in (None, ""))
        group_key = values or ("all-observations",)
        groups[group_key].append(node)
    windows: list[dict[str, Any]] = []
    for position, (group_key, group_nodes) in enumerate(sorted(groups.items(), key=lambda item: str(item[0]))):
        timestamps = [node["timestamp_ms"] for node in group_nodes if node.get("timestamp_ms") is not None]
        windows.append(
            {
                "id": f"window-{position}",
                "group": [str(item) for item in group_key],
                "nodes": sorted(group_nodes, key=lambda node: (node.get("timestamp_ms") is None, node.get("timestamp_ms") or 0, node["index"])),
                "start_ms": min(timestamps) if timestamps else None,
                "end_ms": max(timestamps) if timestamps else None,
            }
        )
    return windows


def _concurrent_span_pairs(nodes: list[dict[str, Any]], edge_keys: set[tuple[str, str, str]]) -> list[dict[str, Any]]:
    spans = [node for node in nodes if node["kind"] == "span"]
    pairs: list[dict[str, Any]] = []
    for left_index, left in enumerate(spans):
        for right in spans[left_index + 1 :]:
            if left.get("trace_id") and right.get("trace_id") and left.get("trace_id") != right.get("trace_id"):
                continue
            if any(
                (left["id"], right["id"], relation) in edge_keys or (right["id"], left["id"], relation) in edge_keys
                for relation in ("parent-child", "span-link", "happens-before")
            ):
                continue
            if _spans_overlap(left, right):
                pairs.append({"left": left["id"], "right": right["id"], "relation": "concurrent"})
    return pairs


def _spans_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_start = left.get("timestamp_ms")
    right_start = right.get("timestamp_ms")
    if left_start is None or right_start is None:
        return False
    left_end = left.get("end_timestamp_ms") if left.get("end_timestamp_ms") is not None else left_start
    right_end = right.get("end_timestamp_ms") if right.get("end_timestamp_ms") is not None else right_start
    return left_start <= right_end and right_start <= left_end


def _format_window_diagram(window: dict[str, Any], edges: list[dict[str, Any]], concurrency: list[dict[str, Any]]) -> dict[str, str]:
    node_ids = {node["id"] for node in window["nodes"]}
    lines = ["flowchart TD"]
    for node in window["nodes"]:
        label = _escape_mermaid_label(node["label"])
        lines.append(f"  {node['id']}[\"{label}\"]")
    relation_labels = {
        "parent-child": "parent",
        "span-link": "link",
        "log-attachment": "log",
        "metric-exemplar": "exemplar",
        "happens-before": "hb",
    }
    for edge in edges:
        if edge["from"] in node_ids and edge["to"] in node_ids:
            lines.append(f"  {edge['from']} -->|{relation_labels.get(edge['relation'], edge['relation'])}| {edge['to']}")
    for pair in concurrency:
        if pair["left"] in node_ids and pair["right"] in node_ids:
            lines.append(f"  {pair['left']} -.-|concurrent| {pair['right']}")
    return {"title": f"{window['id']} group {'/'.join(window['group'])}", "mermaid": "\n".join(lines)}


def _lookup_any(event: dict[str, Any], *names: str) -> Any:
    for name in names:
        if event.get(name) not in (None, ""):
            return event.get(name)
        for container in ("attributes", "fields", "tags"):
            values = event.get(container)
            if isinstance(values, dict) and values.get(name) not in (None, ""):
                return values.get(name)
    return None


def _event_timestamp_ms(event: dict[str, Any]) -> float | None:
    for key in ("timestamp_ms", "time_ms", "start_time_ms"):
        value = event.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    for key in ("time_unix_nano", "start_time_unix_nano"):
        value = event.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value) / 1_000_000
    value = event.get("timestamp") or event.get("time")
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp() * 1000
        except ValueError:
            return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _event_end_timestamp_ms(event: dict[str, Any]) -> float | None:
    for key in ("end_time_ms", "end_timestamp_ms"):
        value = event.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    value = event.get("end_time_unix_nano")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) / 1_000_000
    return None


def _escape_mermaid_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'")
