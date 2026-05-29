from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .loader import ContractLoadError


def load_otlp_json(path: str | Path) -> list[dict[str, Any]]:
    otlp_path = Path(path)
    if not otlp_path.exists():
        raise ContractLoadError(f"OTLP file does not exist: {otlp_path}")
    try:
        payload = json.loads(otlp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractLoadError(f"invalid OTLP JSON in {otlp_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractLoadError(f"OTLP root must be an object: {otlp_path}")
    return list(convert_otlp_payload(payload))


def convert_otlp_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for resource_span in _as_list(payload.get("resourceSpans")):
        resource_attrs = _attributes(resource_span.get("resource", {}).get("attributes", []))
        service = str(resource_attrs.get("service.name", resource_attrs.get("service", "")) or "")
        for scope_span in _as_list(resource_span.get("scopeSpans")) + _as_list(resource_span.get("instrumentationLibrarySpans")):
            for span in _as_list(scope_span.get("spans")):
                if isinstance(span, dict):
                    events.append(_span_event(span, service, resource_attrs))
    for resource_metric in _as_list(payload.get("resourceMetrics")):
        resource_attrs = _attributes(resource_metric.get("resource", {}).get("attributes", []))
        service = str(resource_attrs.get("service.name", resource_attrs.get("service", "")) or "")
        for scope_metric in _as_list(resource_metric.get("scopeMetrics")) + _as_list(resource_metric.get("instrumentationLibraryMetrics")):
            for metric in _as_list(scope_metric.get("metrics")):
                if isinstance(metric, dict):
                    events.extend(_metric_events(metric, service, resource_attrs))
    for resource_log in _as_list(payload.get("resourceLogs")):
        resource_attrs = _attributes(resource_log.get("resource", {}).get("attributes", []))
        service = str(resource_attrs.get("service.name", resource_attrs.get("service", "")) or "")
        for scope_log in _as_list(resource_log.get("scopeLogs")) + _as_list(resource_log.get("instrumentationLibraryLogs")):
            for record in _as_list(scope_log.get("logRecords")):
                if isinstance(record, dict):
                    events.append(_log_event(record, service, resource_attrs))
    return events


def write_jsonl(events: list[dict[str, Any]], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")


def _span_event(span: dict[str, Any], service: str, resource_attrs: dict[str, Any]) -> dict[str, Any]:
    attrs = {**resource_attrs, **_attributes(span.get("attributes", []))}
    return {
        "kind": "span",
        "service": service or attrs.get("service.name"),
        "name": span.get("name"),
        "attributes": attrs,
        "trace_id": span.get("traceId"),
        "span_id": span.get("spanId"),
    }


def _metric_events(metric: dict[str, Any], service: str, resource_attrs: dict[str, Any]) -> list[dict[str, Any]]:
    name = metric.get("name")
    data = metric.get("sum") or metric.get("gauge") or metric.get("histogram") or {}
    points = _as_list(data.get("dataPoints"))
    events: list[dict[str, Any]] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        tags = {**resource_attrs, **_attributes(point.get("attributes", []))}
        value = point.get("asDouble", point.get("asInt", point.get("value")))
        if value is None and "count" in point:
            value = point["count"]
        events.append({"kind": "metric", "service": service or tags.get("service.name"), "name": name, "value": value, "tags": tags})
    return events


def _log_event(record: dict[str, Any], service: str, resource_attrs: dict[str, Any]) -> dict[str, Any]:
    fields = {**resource_attrs, **_attributes(record.get("attributes", []))}
    return {
        "kind": "log",
        "service": service or fields.get("service.name"),
        "name": fields.get("log.name", record.get("eventName", record.get("name", "log"))),
        "severity": record.get("severityText"),
        "message": _body_value(record.get("body")),
        "fields": fields,
        "trace_id": record.get("traceId"),
        "span_id": record.get("spanId"),
    }


def _attributes(raw: Any) -> dict[str, Any]:
    attrs: dict[str, Any] = {}
    for item in _as_list(raw):
        if not isinstance(item, dict) or "key" not in item:
            continue
        attrs[str(item["key"])] = _any_value(item.get("value"))
    return attrs


def _any_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
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
        return _attributes(value["kvlistValue"].get("values", []))
    return None


def _body_value(body: Any) -> str:
    value = _any_value(body)
    return "" if value is None else str(value)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
