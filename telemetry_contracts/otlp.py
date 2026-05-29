from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .loader import ContractLoadError


@dataclass(frozen=True)
class ImportDiagnostic:
    severity: str
    code: str
    message: str
    path: str
    invalidates_contract_claim: bool = False
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "invalidates_contract_claim": self.invalidates_contract_claim,
        }
        if self.details:
            result["details"] = self.details
        return result


_ALIASES: dict[str, tuple[str, ...]] = {
    "resourceSpans": ("resource_spans",),
    "scopeSpans": ("scope_spans",),
    "instrumentationLibrarySpans": ("instrumentation_library_spans",),
    "resourceMetrics": ("resource_metrics",),
    "scopeMetrics": ("scope_metrics",),
    "instrumentationLibraryMetrics": ("instrumentation_library_metrics",),
    "resourceLogs": ("resource_logs",),
    "scopeLogs": ("scope_logs",),
    "instrumentationLibraryLogs": ("instrumentation_library_logs",),
    "logRecords": ("log_records",),
    "traceId": ("trace_id",),
    "spanId": ("span_id",),
    "parentSpanId": ("parent_span_id",),
    "startTimeUnixNano": ("start_time_unix_nano",),
    "endTimeUnixNano": ("end_time_unix_nano",),
    "timeUnixNano": ("time_unix_nano",),
    "observedTimeUnixNano": ("observed_time_unix_nano",),
    "severityText": ("severity_text",),
    "severityNumber": ("severity_number",),
    "eventName": ("event_name",),
    "droppedAttributesCount": ("dropped_attributes_count",),
    "droppedEventsCount": ("dropped_events_count",),
    "droppedLinksCount": ("dropped_links_count",),
    "droppedDataPointsCount": ("dropped_data_points_count",),
    "filteredAttributes": ("filtered_attributes",),
    "asDouble": ("as_double",),
    "asInt": ("as_int",),
    "dataPoints": ("data_points",),
    "aggregationTemporality": ("aggregation_temporality",),
    "isMonotonic": ("is_monotonic",),
    "bucketCounts": ("bucket_counts",),
    "explicitBounds": ("explicit_bounds",),
    "zeroCount": ("zero_count",),
    "quantileValues": ("quantile_values",),
    "schemaUrl": ("schema_url",),
}


def load_otlp_json(path: str | Path) -> list[dict[str, Any]]:
    return load_otlp_json_detailed(path)["events"]


def load_otlp_json_detailed(path: str | Path) -> dict[str, Any]:
    otlp_path = Path(path)
    if not otlp_path.exists():
        raise ContractLoadError(f"OTLP file does not exist: {otlp_path}")
    try:
        payload = json.loads(otlp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractLoadError(f"invalid OTLP JSON in {otlp_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractLoadError(f"OTLP root must be an object: {otlp_path}")
    return convert_otlp_payload_with_diagnostics(payload)


def load_otlp_jsonl_stream(path: str | Path) -> Iterable[dict[str, Any]]:
    otlp_path = Path(path)
    if not otlp_path.exists():
        raise ContractLoadError(f"OTLP JSONL file does not exist: {otlp_path}")

    with otlp_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            report = convert_otlp_payload_with_diagnostics(payload, root_path=f"$[{line_number}]")
            yield from report["events"]


def load_otlp_jsonl_detailed(path: str | Path) -> dict[str, Any]:
    otlp_path = Path(path)
    if not otlp_path.exists():
        raise ContractLoadError(f"OTLP JSONL file does not exist: {otlp_path}")

    events: list[dict[str, Any]] = []
    diagnostics: list[ImportDiagnostic] = []
    records = 0
    with otlp_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            records += 1
            record_path = f"$[{line_number}]"
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                diagnostics.append(
                    ImportDiagnostic(
                        "error",
                        "otlp.malformed_record",
                        f"skipped malformed OTLP JSONL record: {exc.msg}",
                        record_path,
                        True,
                        {"line": line_number},
                    )
                )
                continue
            if not isinstance(payload, dict):
                diagnostics.append(
                    ImportDiagnostic(
                        "error",
                        "otlp.malformed_record",
                        "skipped OTLP JSONL record because it is not an object",
                        record_path,
                        True,
                        {"line": line_number},
                    )
                )
                continue
            report = convert_otlp_payload_with_diagnostics(payload, root_path=record_path)
            events.extend(report["events"])
            diagnostics.extend(ImportDiagnostic(**item) for item in report["diagnostics"])
    return _report(events, diagnostics, records=records, streaming=True)


def convert_otlp_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return convert_otlp_payload_with_diagnostics(payload)["events"]


def convert_otlp_payload_with_diagnostics(payload: dict[str, Any], root_path: str = "$") -> dict[str, Any]:
    diagnostics: list[ImportDiagnostic] = []
    events: list[dict[str, Any]] = []

    for resource_span, resource_path in _list_items(payload, "resourceSpans", root_path, diagnostics):
        if not isinstance(resource_span, dict):
            _skip(diagnostics, f"{resource_path}", "resourceSpans entry is not an object")
            continue
        resource = _resource(resource_span, resource_path, diagnostics)
        for scope_span, scope_path in _scope_items(resource_span, "scopeSpans", "instrumentationLibrarySpans", resource_path, diagnostics):
            for span, span_path in _list_items(scope_span, "spans", scope_path, diagnostics):
                if isinstance(span, dict):
                    events.append(_span_event(span, resource, _scope(scope_span, scope_path, diagnostics), span_path, diagnostics))
                else:
                    _skip(diagnostics, span_path, "span entry is not an object")

    for resource_metric, resource_path in _list_items(payload, "resourceMetrics", root_path, diagnostics):
        if not isinstance(resource_metric, dict):
            _skip(diagnostics, resource_path, "resourceMetrics entry is not an object")
            continue
        resource = _resource(resource_metric, resource_path, diagnostics)
        for scope_metric, scope_path in _scope_items(resource_metric, "scopeMetrics", "instrumentationLibraryMetrics", resource_path, diagnostics):
            for metric, metric_path in _list_items(scope_metric, "metrics", scope_path, diagnostics):
                if isinstance(metric, dict):
                    events.extend(_metric_events(metric, resource, _scope(scope_metric, scope_path, diagnostics), metric_path, diagnostics))
                else:
                    _skip(diagnostics, metric_path, "metric entry is not an object")

    for resource_log, resource_path in _list_items(payload, "resourceLogs", root_path, diagnostics):
        if not isinstance(resource_log, dict):
            _skip(diagnostics, resource_path, "resourceLogs entry is not an object")
            continue
        resource = _resource(resource_log, resource_path, diagnostics)
        for scope_log, scope_path in _scope_items(resource_log, "scopeLogs", "instrumentationLibraryLogs", resource_path, diagnostics):
            for record, record_path in _list_items(scope_log, "logRecords", scope_path, diagnostics):
                if isinstance(record, dict):
                    events.append(_log_event(record, resource, _scope(scope_log, scope_path, diagnostics), record_path, diagnostics))
                else:
                    _skip(diagnostics, record_path, "logRecords entry is not an object")

    _unsupported_top_level(payload, root_path, diagnostics)
    return _report(events, diagnostics, records=1, streaming=False)


def write_jsonl(events: list[dict[str, Any]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")


def write_diagnostics(report: dict[str, Any], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"summary": report["summary"], "diagnostics": report["diagnostics"]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def convert_events_to_otlp_payload(events: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {"resourceSpans": [], "resourceMetrics": [], "resourceLogs": []}
    for event in events:
        if not isinstance(event, dict):
            continue
        kind = event.get("kind")
        service = str(event.get("service") or event.get("attributes", {}).get("service.name") or event.get("tags", {}).get("service.name") or event.get("fields", {}).get("service.name") or "")
        resource = {"attributes": _otlp_attributes({"service.name": service} if service else {})}
        scope = event.get("scope") if isinstance(event.get("scope"), dict) else {}
        scope_obj = {key: value for key, value in {"name": scope.get("name", "telemetry-contracts.roundtrip"), "version": scope.get("version")}.items() if value}
        if kind == "span":
            payload["resourceSpans"].append({"resource": resource, "scopeSpans": [{"scope": scope_obj, "spans": [_event_to_otlp_span(event)]}]})
        elif kind == "metric":
            metric_type = str(event.get("metric_type") or "gauge")
            payload["resourceMetrics"].append({"resource": resource, "scopeMetrics": [{"scope": scope_obj, "metrics": [_event_to_otlp_metric(event, metric_type)]}]})
        elif kind == "log":
            payload["resourceLogs"].append({"resource": resource, "scopeLogs": [{"scope": scope_obj, "logRecords": [_event_to_otlp_log(event)]}]})
    return {key: value for key, value in payload.items() if value}


def analyze_otlp_report(report: dict[str, Any], cardinality_threshold: int = 2) -> dict[str, Any]:
    events = [event for event in report.get("events", []) if isinstance(event, dict)]
    diagnostics = [item for item in report.get("diagnostics", []) if isinstance(item, dict)]
    values_by_key: dict[str, set[str]] = {}
    pii: list[dict[str, Any]] = []
    temporality: dict[str, int] = {}
    missing_temporality: list[str] = []
    schemas: dict[str, int] = {}
    for index, event in enumerate(events):
        attrs = _event_attrs(event)
        for key, value in attrs.items():
            values_by_key.setdefault(key, set()).add(str(value))
            risk = _pii_secret_risk(key, value)
            if risk:
                pii.append({"event_index": index, "kind": event.get("kind"), "field": key, "risk": risk, "value_preview": _safe_preview(value)})
        for scope_name in ("resource", "scope"):
            schema = event.get(scope_name, {}).get("schema_url") if isinstance(event.get(scope_name), dict) else None
            if schema:
                schemas[str(schema)] = schemas.get(str(schema), 0) + 1
        if event.get("kind") == "metric":
            temp = event.get("aggregation_temporality")
            if temp:
                temporality[str(temp)] = temporality.get(str(temp), 0) + 1
            elif event.get("metric_type") in {"sum", "histogram", "exponentialHistogram"}:
                missing_temporality.append(str(event.get("name", "metric")))
    cardinality = [
        {"field": key, "distinct_values": len(values), "risk": "high_cardinality_label"}
        for key, values in sorted(values_by_key.items())
        if len(values) > cardinality_threshold or re.search(r"(user|tenant|session|request|trace|span|cart|account).*id$", key)
    ]
    unsupported = [item for item in diagnostics if str(item.get("code")) in {"otlp.unsupported_metric", "otlp.unsupported_top_level", "otlp.skipped_record", "otlp.malformed_record"}]
    dropped = [item for item in diagnostics if str(item.get("code")) == "otlp.dropped_evidence"]
    unknown_schemas = [{"schema_url": key, "events": value} for key, value in sorted(schemas.items()) if not key.startswith("https://opentelemetry.io/schemas/")]
    risk_count = len(dropped) + len(cardinality) + len(pii) + len(missing_temporality) + len(unsupported) + len(unknown_schemas)
    return {
        "summary": {
            **report.get("summary", {}),
            "collector_risk_count": risk_count,
            "dropped_evidence": len(dropped),
            "cardinality_risks": len(cardinality),
            "pii_secret_risks": len(pii),
            "unsupported_features": len(unsupported),
            "unknown_schemas": len(unknown_schemas),
            "missing_temporality": len(missing_temporality),
        },
        "dropped_fields": dropped,
        "unknown_schemas": unknown_schemas,
        "cardinality_risks": cardinality,
        "pii_secret_risks": pii,
        "temporality": {"counts": dict(sorted(temporality.items())), "missing_for_metrics": sorted(set(missing_temporality))},
        "unsupported_features": unsupported,
        "limitations": [
            "Cardinality is estimated over the supplied finite export, not backend-wide production series.",
            "PII/secret risk checks are heuristic field-name and value-pattern checks for triage.",
            "Unsupported-feature diagnostics bound the validity of contract claims made from this export.",
        ],
    }


def format_collector_analysis_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Collector export analysis",
        "",
        f"- Events: {summary.get('events', 0)}",
        f"- Diagnostics: {summary.get('diagnostics', 0)}",
        f"- Invalidating diagnostics: {summary.get('invalidating_diagnostics', 0)}",
        f"- Collector risk count: {summary.get('collector_risk_count', 0)}",
        f"- Dropped evidence: {summary.get('dropped_evidence', 0)}",
        f"- Cardinality risks: {summary.get('cardinality_risks', 0)}",
        f"- PII/secret risks: {summary.get('pii_secret_risks', 0)}",
        f"- Unsupported features: {summary.get('unsupported_features', 0)}",
        f"- Unknown schemas: {summary.get('unknown_schemas', 0)}",
        f"- Missing temporality: {summary.get('missing_temporality', 0)}",
        "",
        "## Temporality",
        "",
        f"- Counts: `{json.dumps(report.get('temporality', {}).get('counts', {}), sort_keys=True)}`",
        f"- Missing for metrics: `{json.dumps(report.get('temporality', {}).get('missing_for_metrics', []), sort_keys=True)}`",
        "",
    ]
    for section, title in (
        ("dropped_fields", "Dropped evidence"),
        ("cardinality_risks", "Cardinality risks"),
        ("pii_secret_risks", "PII/secret risks"),
        ("unknown_schemas", "Unknown schemas"),
        ("unsupported_features", "Unsupported OTLP features"),
    ):
        lines.extend([f"## {title}", ""])
        items = report.get(section, [])
        if not items:
            lines.append("None.")
        else:
            for item in items:
                lines.append(f"- `{json.dumps(item, sort_keys=True)}`")
        lines.append("")
    lines.extend(["## Limitations", ""])
    lines.extend(f"- {item}" for item in report.get("limitations", []))
    lines.append("")
    return "\n".join(lines)


def _event_to_otlp_span(event: dict[str, Any]) -> dict[str, Any]:
    span = {
        "traceId": event.get("trace_id"),
        "spanId": event.get("span_id"),
        "parentSpanId": event.get("parent_span_id"),
        "name": event.get("name"),
        "kind": event.get("span_kind"),
        "startTimeUnixNano": _string_int(event.get("start_time_unix_nano")),
        "endTimeUnixNano": _string_int(event.get("end_time_unix_nano")),
        "attributes": _otlp_attributes(event.get("attributes", {})),
        "status": event.get("status"),
    }
    span_events = []
    for item in event.get("events", []) if isinstance(event.get("events"), list) else []:
        if isinstance(item, dict):
            span_events.append({"name": item.get("name"), "timeUnixNano": _string_int(item.get("time_unix_nano")), "attributes": _otlp_attributes(item.get("attributes", {}))})
    if span_events:
        span["events"] = span_events
    links = []
    for item in event.get("links", []) if isinstance(event.get("links"), list) else []:
        if isinstance(item, dict):
            links.append({"traceId": item.get("trace_id"), "spanId": item.get("span_id"), "attributes": _otlp_attributes(item.get("attributes", {}))})
    if links:
        span["links"] = links
    return _drop_none(span)


def _event_to_otlp_metric(event: dict[str, Any], metric_type: str) -> dict[str, Any]:
    point = {
        "attributes": _otlp_attributes(event.get("tags", {})),
        "startTimeUnixNano": _string_int(event.get("start_time_unix_nano")),
        "timeUnixNano": _string_int(event.get("time_unix_nano")),
        "traceId": event.get("trace_id"),
        "spanId": event.get("span_id"),
    }
    if metric_type in {"sum", "gauge"}:
        point["asDouble" if isinstance(event.get("value"), float) else "asInt"] = event.get("value")
    elif metric_type == "histogram":
        point.update({"count": _string_int(event.get("count")), "sum": event.get("sum", event.get("value")), "min": event.get("min"), "max": event.get("max"), "bucketCounts": [_string_int(v) for v in event.get("bucket_counts", [])], "explicitBounds": event.get("explicit_bounds", [])})
    elif metric_type == "exponentialHistogram":
        point.update({"count": _string_int(event.get("count")), "sum": event.get("sum", event.get("value")), "min": event.get("min"), "max": event.get("max"), "scale": event.get("scale"), "zeroCount": _string_int(event.get("zero_count")), "positive": event.get("positive"), "negative": event.get("negative")})
    elif metric_type == "summary":
        point.update({"count": _string_int(event.get("count")), "sum": event.get("sum", event.get("value")), "quantileValues": event.get("quantiles", [])})
    exemplars = []
    for item in event.get("exemplars", []) if isinstance(event.get("exemplars"), list) else []:
        if isinstance(item, dict):
            exemplar = {"timeUnixNano": _string_int(item.get("time_unix_nano")), "asDouble": item.get("value"), "traceId": item.get("trace_id"), "spanId": item.get("span_id"), "filteredAttributes": _otlp_attributes(item.get("filtered_attributes", {}))}
            exemplars.append(_drop_none(exemplar))
    if exemplars:
        point["exemplars"] = exemplars
    data = {"dataPoints": [_drop_none(point)]}
    if event.get("aggregation_temporality"):
        data["aggregationTemporality"] = event.get("aggregation_temporality")
    if event.get("is_monotonic") is not None:
        data["isMonotonic"] = event.get("is_monotonic")
    return _drop_none({"name": event.get("name"), "description": event.get("description"), "unit": event.get("unit"), metric_type: data})


def _event_to_otlp_log(event: dict[str, Any]) -> dict[str, Any]:
    fields = dict(event.get("fields", {})) if isinstance(event.get("fields"), dict) else {}
    if event.get("name"):
        fields.setdefault("log.name", event.get("name"))
    body = event.get("body")
    if body is None and event.get("message"):
        body = event.get("message")
    return _drop_none(
        {
            "timeUnixNano": _string_int(event.get("time_unix_nano")),
            "observedTimeUnixNano": _string_int(event.get("observed_time_unix_nano")),
            "severityText": event.get("severity"),
            "severityNumber": event.get("severity_number"),
            "traceId": event.get("trace_id"),
            "spanId": event.get("span_id"),
            "body": _otlp_any_value(body),
            "attributes": _otlp_attributes(fields),
        }
    )


def _otlp_attributes(attrs: Any) -> list[dict[str, Any]]:
    if not isinstance(attrs, dict):
        return []
    return [{"key": str(key), "value": _otlp_any_value(value)} for key, value in sorted(attrs.items()) if value is not None]


def _otlp_any_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int) and not isinstance(value, bool):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [_otlp_any_value(item) for item in value]}}
    if isinstance(value, dict):
        return {"kvlistValue": {"values": _otlp_attributes(value)}}
    return {"stringValue": "" if value is None else str(value)}


def _string_int(value: Any) -> str | None:
    if value is None:
        return None
    return str(int(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)


def _event_attrs(event: dict[str, Any]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for key in ("attributes", "tags", "fields"):
        if isinstance(event.get(key), dict):
            attrs.update(event[key])
    return attrs


def _pii_secret_risk(key: str, value: Any) -> str | None:
    text = str(value)
    if re.search(r"(password|passwd|secret|token|api[_-]?key|authorization|credential|cookie)", key, re.I):
        return "sensitive_field_name"
    if re.search(r"Bearer\s+[A-Za-z0-9._-]+|eyJ[A-Za-z0-9._-]+|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
        return "sensitive_value_pattern"
    return None


def _safe_preview(value: Any) -> str:
    text = str(value)
    if len(text) <= 12:
        return text
    return text[:4] + "…" + text[-4:]


def _span_event(span: dict[str, Any], resource: dict[str, Any], scope: dict[str, Any], path: str, diagnostics: list[ImportDiagnostic]) -> dict[str, Any]:
    attrs = {**resource["attributes"], **_attributes(_get(span, "attributes", path, diagnostics), f"{path}.attributes", diagnostics)}
    event = {
        "kind": "span",
        "service": resource["service"] or attrs.get("service.name"),
        "name": _get(span, "name", path, diagnostics),
        "attributes": attrs,
        "trace_id": _get(span, "traceId", path, diagnostics),
        "span_id": _get(span, "spanId", path, diagnostics),
        "parent_span_id": _get(span, "parentSpanId", path, diagnostics),
        "span_kind": _get(span, "kind", path, diagnostics),
        "start_time_unix_nano": _number(_get(span, "startTimeUnixNano", path, diagnostics)),
        "end_time_unix_nano": _number(_get(span, "endTimeUnixNano", path, diagnostics)),
        "timestamp_ms": _unix_nano_to_ms(_get(span, "startTimeUnixNano", path, diagnostics)),
        "end_time_ms": _unix_nano_to_ms(_get(span, "endTimeUnixNano", path, diagnostics)),
        "status": _status(_get(span, "status", path, diagnostics)),
        "events": _span_events(_get(span, "events", path, diagnostics), f"{path}.events", diagnostics),
        "links": _span_links(_get(span, "links", path, diagnostics), f"{path}.links", diagnostics),
        "resource": resource,
        "scope": scope,
        "source_json_path": path,
    }
    _dropped_counts(span, path, diagnostics)
    return _drop_none(event)


def _metric_events(metric: dict[str, Any], resource: dict[str, Any], scope: dict[str, Any], path: str, diagnostics: list[ImportDiagnostic]) -> list[dict[str, Any]]:
    name = _get(metric, "name", path, diagnostics)
    metric_type, data = _metric_data(metric)
    points = _as_list(_get(data, "dataPoints", f"{path}.{metric_type}", diagnostics))
    events: list[dict[str, Any]] = []
    for index, point in enumerate(points):
        point_path = f"{path}.{metric_type}.dataPoints[{index}]"
        if not isinstance(point, dict):
            _skip(diagnostics, point_path, "metric data point is not an object")
            continue
        tags = {**resource["attributes"], **_attributes(_get(point, "attributes", point_path, diagnostics), f"{point_path}.attributes", diagnostics)}
        exemplars = _exemplars(_get(point, "exemplars", point_path, diagnostics), f"{point_path}.exemplars", diagnostics)
        exemplar_trace = next((item for item in exemplars if item.get("trace_id")), {})
        event = {
            "kind": "metric",
            "service": resource["service"] or tags.get("service.name"),
            "name": name,
            "value": _metric_value(metric_type, point),
            "tags": tags,
            "metric_type": metric_type,
            "description": _get(metric, "description", path, diagnostics),
            "unit": _get(metric, "unit", path, diagnostics),
            "trace_id": _get(point, "traceId", point_path, diagnostics) or exemplar_trace.get("trace_id"),
            "span_id": _get(point, "spanId", point_path, diagnostics) or exemplar_trace.get("span_id"),
            "exemplars": exemplars,
            "resource": resource,
            "scope": scope,
            "source_json_path": point_path,
        }
        for key, value in _metric_point_metadata(metric_type, data, point, point_path, diagnostics).items():
            if value is not None:
                event[key] = value
        events.append(_drop_none(event))
    if metric_type == "unknown":
        diagnostics.append(ImportDiagnostic("warning", "otlp.unsupported_metric", f"unsupported metric payload for {name}", path, True))
    return events


def _metric_data(metric: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    for metric_type in ("sum", "gauge", "histogram", "exponentialHistogram", "summary"):
        data = metric.get(metric_type)
        if isinstance(data, dict):
            return metric_type, data
    return "unknown", {}


def _metric_value(metric_type: str, point: dict[str, Any]) -> Any:
    if metric_type in {"sum", "gauge"}:
        return _number(_get_no_diag(point, "asDouble", _get_no_diag(point, "asInt", _get_no_diag(point, "value"))))
    if metric_type in {"histogram", "exponentialHistogram", "summary"}:
        return _number(_get_no_diag(point, "sum", _get_no_diag(point, "count")))
    return _number(_get_no_diag(point, "value"))


def _metric_point_metadata(metric_type: str, data: dict[str, Any], point: dict[str, Any], path: str, diagnostics: list[ImportDiagnostic]) -> dict[str, Any]:
    common = {
        "aggregation_temporality": _get(data, "aggregationTemporality", path.rsplit(".", 1)[0], diagnostics),
        "is_monotonic": _get(data, "isMonotonic", path.rsplit(".", 1)[0], diagnostics),
        "start_time_unix_nano": _number(_get(point, "startTimeUnixNano", path, diagnostics)),
        "time_unix_nano": _number(_get(point, "timeUnixNano", path, diagnostics)),
        "timestamp_ms": _unix_nano_to_ms(_get(point, "timeUnixNano", path, diagnostics)),
    }
    if metric_type == "histogram":
        common.update(
            {
                "count": _number(_get(point, "count", path, diagnostics)),
                "sum": _number(_get(point, "sum", path, diagnostics)),
                "min": _number(_get(point, "min", path, diagnostics)),
                "max": _number(_get(point, "max", path, diagnostics)),
                "bucket_counts": [_number(item) for item in _as_list(_get(point, "bucketCounts", path, diagnostics))],
                "explicit_bounds": [_number(item) for item in _as_list(_get(point, "explicitBounds", path, diagnostics))],
            }
        )
    elif metric_type == "exponentialHistogram":
        common.update(
            {
                "count": _number(_get(point, "count", path, diagnostics)),
                "sum": _number(_get(point, "sum", path, diagnostics)),
                "min": _number(_get(point, "min", path, diagnostics)),
                "max": _number(_get(point, "max", path, diagnostics)),
                "scale": _number(_get(point, "scale", path, diagnostics)),
                "zero_count": _number(_get(point, "zeroCount", path, diagnostics)),
                "positive": _get(point, "positive", path, diagnostics),
                "negative": _get(point, "negative", path, diagnostics),
            }
        )
    elif metric_type == "summary":
        common.update(
            {
                "count": _number(_get(point, "count", path, diagnostics)),
                "sum": _number(_get(point, "sum", path, diagnostics)),
                "quantiles": [
                    {"quantile": _number(_get_no_diag(item, "quantile")), "value": _number(_get_no_diag(item, "value"))}
                    for item in _as_list(_get(point, "quantileValues", path, diagnostics))
                    if isinstance(item, dict)
                ],
            }
        )
    return common


def _log_event(record: dict[str, Any], resource: dict[str, Any], scope: dict[str, Any], path: str, diagnostics: list[ImportDiagnostic]) -> dict[str, Any]:
    fields = {**resource["attributes"], **_attributes(_get(record, "attributes", path, diagnostics), f"{path}.attributes", diagnostics)}
    body = _body_value(_get(record, "body", path, diagnostics))
    if isinstance(body, dict):
        fields = {**body, **fields}
    event = {
        "kind": "log",
        "service": resource["service"] or fields.get("service.name"),
        "name": fields.get("log.name", _get(record, "eventName", path, diagnostics) or _get(record, "name", path, diagnostics) or "log"),
        "severity": _get(record, "severityText", path, diagnostics),
        "severity_number": _number(_get(record, "severityNumber", path, diagnostics)),
        "message": _message_from_body(body),
        "body": body,
        "fields": fields,
        "trace_id": _get(record, "traceId", path, diagnostics),
        "span_id": _get(record, "spanId", path, diagnostics),
        "time_unix_nano": _number(_get(record, "timeUnixNano", path, diagnostics)),
        "observed_time_unix_nano": _number(_get(record, "observedTimeUnixNano", path, diagnostics)),
        "timestamp_ms": _unix_nano_to_ms(_get(record, "timeUnixNano", path, diagnostics) or _get(record, "observedTimeUnixNano", path, diagnostics)),
        "resource": resource,
        "scope": scope,
        "source_json_path": path,
    }
    _dropped_counts(record, path, diagnostics)
    return _drop_none(event)


def _message_from_body(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, dict) and "message" in body:
        return str(body["message"])
    return str(body)


def _resource(container: dict[str, Any], path: str, diagnostics: list[ImportDiagnostic]) -> dict[str, Any]:
    resource = _get(container, "resource", path, diagnostics)
    attrs = _attributes(_get(resource, "attributes", f"{path}.resource", diagnostics) if isinstance(resource, dict) else [], f"{path}.resource.attributes", diagnostics)
    result = {
        "attributes": attrs,
        "service": str(attrs.get("service.name", attrs.get("service", "")) or ""),
        "schema_url": _get(resource, "schemaUrl", f"{path}.resource", diagnostics) if isinstance(resource, dict) else None,
        "source_json_path": f"{path}.resource" if isinstance(resource, dict) else path,
    }
    return _drop_none(result)


def _scope(scope_container: dict[str, Any], path: str, diagnostics: list[ImportDiagnostic]) -> dict[str, Any]:
    scope = _get(scope_container, "scope", path, diagnostics) or _get(scope_container, "instrumentationLibrary", path, diagnostics) or {}
    if not isinstance(scope, dict):
        _skip(diagnostics, f"{path}.scope", "scope metadata is not an object")
        scope = {}
    attrs = _attributes(_get(scope, "attributes", f"{path}.scope", diagnostics), f"{path}.scope.attributes", diagnostics)
    result = {
        "name": _get(scope, "name", f"{path}.scope", diagnostics),
        "version": _get(scope, "version", f"{path}.scope", diagnostics),
        "attributes": attrs,
        "schema_url": _get(scope_container, "schemaUrl", path, diagnostics),
        "source_json_path": f"{path}.scope",
    }
    return _drop_none(result)


def _span_events(raw: Any, path: str, diagnostics: list[ImportDiagnostic]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, item in enumerate(_as_list(raw)):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            _skip(diagnostics, item_path, "span event is not an object")
            continue
        events.append(
            _drop_none(
                {
                    "name": _get(item, "name", item_path, diagnostics),
                    "time_unix_nano": _number(_get(item, "timeUnixNano", item_path, diagnostics)),
                    "timestamp_ms": _unix_nano_to_ms(_get(item, "timeUnixNano", item_path, diagnostics)),
                    "attributes": _attributes(_get(item, "attributes", item_path, diagnostics), f"{item_path}.attributes", diagnostics),
                    "source_json_path": item_path,
                }
            )
        )
    return events


def _span_links(raw: Any, path: str, diagnostics: list[ImportDiagnostic]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for index, item in enumerate(_as_list(raw)):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            _skip(diagnostics, item_path, "span link is not an object")
            continue
        links.append(
            _drop_none(
                {
                    "trace_id": _get(item, "traceId", item_path, diagnostics),
                    "span_id": _get(item, "spanId", item_path, diagnostics),
                    "attributes": _attributes(_get(item, "attributes", item_path, diagnostics), f"{item_path}.attributes", diagnostics),
                    "source_json_path": item_path,
                }
            )
        )
    return links


def _exemplars(raw: Any, path: str, diagnostics: list[ImportDiagnostic]) -> list[dict[str, Any]]:
    exemplars: list[dict[str, Any]] = []
    for index, item in enumerate(_as_list(raw)):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            _skip(diagnostics, item_path, "metric exemplar is not an object")
            continue
        exemplars.append(
            _drop_none(
                {
                    "trace_id": _get(item, "traceId", item_path, diagnostics),
                    "span_id": _get(item, "spanId", item_path, diagnostics),
                    "time_unix_nano": _number(_get(item, "timeUnixNano", item_path, diagnostics)),
                    "timestamp_ms": _unix_nano_to_ms(_get(item, "timeUnixNano", item_path, diagnostics)),
                    "value": _number(_get(item, "asDouble", item_path, diagnostics) or _get(item, "asInt", item_path, diagnostics)),
                    "filtered_attributes": _attributes(_get(item, "filteredAttributes", item_path, diagnostics), f"{item_path}.filteredAttributes", diagnostics),
                    "source_json_path": item_path,
                }
            )
        )
    return exemplars


def _status(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return _drop_none({"code": raw.get("code"), "message": raw.get("message")})


def _attributes(raw: Any, path: str, diagnostics: list[ImportDiagnostic]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for index, item in enumerate(_as_list(raw)):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict) or "key" not in item:
            _skip(diagnostics, item_path, "attribute entry is not an object with a key")
            continue
        attrs[str(item["key"])] = _any_value(_get(item, "value", item_path, diagnostics))
    return attrs


def _any_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for key in ("stringValue", "intValue", "doubleValue", "boolValue", "bytesValue"):
        if key in value:
            raw = value[key]
            if key == "intValue":
                return int(raw)
            if key == "doubleValue":
                return float(raw)
            return raw
    if "arrayValue" in value:
        return [_any_value(item) for item in _as_list(value["arrayValue"].get("values"))]
    if "kvlistValue" in value:
        return _attributes(value["kvlistValue"].get("values", []), "$.kvlistValue.values", [])
    return None


def _body_value(body: Any) -> Any:
    return _any_value(body)


def _scope_items(container: dict[str, Any], canonical: str, legacy: str, path: str, diagnostics: list[ImportDiagnostic]) -> Iterable[tuple[dict[str, Any], str]]:
    yield from _list_items(container, canonical, path, diagnostics)
    yield from _list_items(container, legacy, path, diagnostics)


def _list_items(container: dict[str, Any], canonical: str, path: str, diagnostics: list[ImportDiagnostic]) -> Iterable[tuple[Any, str]]:
    raw = _get(container, canonical, path, diagnostics)
    if raw is None:
        return
    if not isinstance(raw, list):
        _skip(diagnostics, f"{path}.{canonical}", f"{canonical} is not a list")
        return
    for index, item in enumerate(raw):
        yield item, f"{path}.{canonical}[{index}]"


def _get(container: Any, canonical: str, path: str, diagnostics: list[ImportDiagnostic]) -> Any:
    if not isinstance(container, dict):
        return None
    if canonical in container:
        return container[canonical]
    for alias in _ALIASES.get(canonical, ()):
        if alias in container:
            diagnostics.append(
                ImportDiagnostic(
                    "info",
                    "otlp.normalized_alias",
                    f"normalized OTLP alias {alias!r} to {canonical!r}",
                    f"{path}.{alias}",
                    False,
                    {"canonical": canonical, "alias": alias},
                )
            )
            return container[alias]
    return None


def _get_no_diag(container: Any, canonical: str, default: Any = None) -> Any:
    if not isinstance(container, dict):
        return default
    if canonical in container:
        return container[canonical]
    for alias in _ALIASES.get(canonical, ()):
        if alias in container:
            return container[alias]
    return default


def _skip(diagnostics: list[ImportDiagnostic], path: str, message: str) -> None:
    diagnostics.append(ImportDiagnostic("warning", "otlp.skipped_record", message, path, True))


def _dropped_counts(container: dict[str, Any], path: str, diagnostics: list[ImportDiagnostic]) -> None:
    for key in ("droppedAttributesCount", "droppedEventsCount", "droppedLinksCount", "droppedDataPointsCount"):
        value = _number(_get(container, key, path, diagnostics))
        if isinstance(value, (int, float)) and value:
            diagnostics.append(
                ImportDiagnostic(
                    "warning",
                    "otlp.dropped_evidence",
                    f"{key}={value} indicates collector/exporter loss",
                    f"{path}.{key}",
                    True,
                    {"count": value, "field": key},
                )
            )


def _unsupported_top_level(payload: dict[str, Any], path: str, diagnostics: list[ImportDiagnostic]) -> None:
    supported = {"resourceSpans", "resource_spans", "resourceMetrics", "resource_metrics", "resourceLogs", "resource_logs"}
    for key in sorted(payload):
        if key not in supported:
            diagnostics.append(ImportDiagnostic("info", "otlp.unsupported_top_level", f"ignored unsupported top-level OTLP field {key!r}", f"{path}.{key}", False))


def _report(events: list[dict[str, Any]], diagnostics: list[ImportDiagnostic], records: int, streaming: bool) -> dict[str, Any]:
    invalidating = sum(1 for item in diagnostics if item.invalidates_contract_claim)
    return {
        "summary": {
            "records": records,
            "events": len(events),
            "diagnostics": len(diagnostics),
            "invalidating_diagnostics": invalidating,
            "streaming": streaming,
            "events_by_kind": _counts(event.get("kind") for event in events),
            "diagnostics_by_code": _counts(item.code for item in diagnostics),
        },
        "events": events,
        "diagnostics": [item.to_dict() for item in diagnostics],
    }


def _counts(values: Iterable[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _number(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value
    return value


def _unix_nano_to_ms(value: Any) -> int | None:
    numeric = _number(value)
    if isinstance(numeric, (int, float)):
        return int(numeric / 1_000_000)
    return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _drop_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}
