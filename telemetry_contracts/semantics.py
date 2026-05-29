from __future__ import annotations

from collections import Counter, defaultdict
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
    return "\n".join(lines)
