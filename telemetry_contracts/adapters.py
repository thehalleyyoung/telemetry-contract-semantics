"""Bring-your-own-data adapters.

The rest of the toolkit speaks one native event shape::

    {"kind": "span|metric|log", "service": ..., "name": ...,
     "attributes": {...}, "trace_id": ..., "timestamp_ms": ...}

Most teams do *not* emit that exact shape today. They have JSON log lines from
``logging``/logrus/zap/pino/winston, Datadog-style ``dd.trace_id`` fields, or
OTLP collector exports. This module normalizes those shapes into the native
event model heuristically, with no contract and no relabeling required, so the
tool can be used right now with the data you already have.

Normalization is deliberately conservative and self-describing:

* The inferred ``kind`` carries ``_kind_confidence`` and ``_kind_reason`` and
  falls back to the neutral ``event`` kind when the shape is ambiguous, so
  contract-free checks can skip kind-specific heuristics on low-confidence rows.
* Original keys are preserved under ``attributes`` (nothing is silently
  dropped) and alias collisions are reported as normalization diagnostics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .loader import ContractLoadError

NATIVE_KINDS = {"span", "metric", "log"}

# Alias tables, highest precedence first. Lookups are case-insensitive and also
# match dotted/resource-prefixed variants (e.g. ``resource.service.name``).
_SERVICE_ALIASES = ["service", "service_name", "service.name", "servicename", "resource.service.name", "app", "application", "logger_name"]
_NAME_ALIASES = ["name", "operation", "operation_name", "operationname", "span_name", "span.name", "event_name", "event", "logger", "metric", "metric_name"]
_TRACE_ALIASES = ["trace_id", "traceid", "trace.id", "dd.trace_id", "oteltraceid", "tid"]
_SPAN_ALIASES = ["span_id", "spanid", "span.id", "dd.span_id", "otelspanid"]
_REQUEST_ALIASES = ["request_id", "requestid", "req_id", "reqid", "http.request_id", "x_request_id", "x-request-id", "correlation_id", "correlationid"]
_TIMESTAMP_MS_ALIASES = ["timestamp_ms", "time_ms", "timestampmillis", "epoch_ms"]
_TIMESTAMP_ALIASES = ["timestamp", "time", "ts", "@timestamp", "eventtime", "datetime", "asctime"]
_SEVERITY_ALIASES = ["severity", "severitytext", "level", "levelname", "log.level", "loglevel", "lvl"]
_MESSAGE_ALIASES = ["message", "msg", "body", "log", "event"]
_VALUE_ALIASES = ["value", "metric_value", "metricvalue", "val"]
_KIND_ALIASES = ["kind", "type", "signal", "telemetry_type"]
_DURATION_ALIASES = ["duration_ms", "duration", "elapsed_ms", "latency_ms", "took_ms"]

# Keys that we lift to the top level and therefore should not duplicate inside
# the attributes bag.
_CONSUMED_TOP_LEVEL = {"attributes", "tags", "fields", "_line"}


def load_events_auto(path: str | Path, *, tolerant: bool = False) -> dict[str, Any]:
    """Load telemetry of *whatever shape you already have* into native events.

    Supports the native JSONL shape, arbitrary JSON-object log lines (JSONL),
    a single JSON array of log objects, logfmt (``key=value``) lines, and OTLP
    JSON/JSONL exports. Returns a dict with ``events`` plus normalization
    ``diagnostics`` and ``summary`` so callers can surface what was inferred.

    When ``tolerant`` is true, lines that are neither JSON nor logfmt are
    skipped (recorded as diagnostics) instead of raising. This is what the
    repository scanner uses so a single messy file does not abort a whole scan.
    """

    source = Path(path)
    if not source.exists():
        raise ContractLoadError(f"telemetry file does not exist: {source}")
    text = source.read_text(encoding="utf-8", errors="replace")
    raw_records, fmt, parse_diagnostics = _parse_records(text, source, tolerant=tolerant)
    if fmt == "otlp":
        from .otlp import load_otlp_json_detailed, load_otlp_jsonl_detailed

        detailed = load_otlp_jsonl_detailed(source) if source.suffix.lower() == ".jsonl" else load_otlp_json_detailed(source)
        events = detailed.get("events", []) if isinstance(detailed, dict) else list(detailed)
        for line_number, event in enumerate(events, start=1):
            event.setdefault("_line", line_number)
        return {
            "events": events,
            "format": "otlp",
            "diagnostics": detailed.get("diagnostics", []) if isinstance(detailed, dict) else [],
            "summary": _summarize(events),
        }
    result = normalize_events(raw_records, source_format=fmt)
    result["diagnostics"] = parse_diagnostics + result["diagnostics"]
    return result


def normalize_events(raw_records: list[dict[str, Any]], *, source_format: str = "json") -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for line_number, record in enumerate(raw_records, start=1):
        event, record_diagnostics = normalize_event(record, line_number=line_number)
        events.append(event)
        diagnostics.extend(record_diagnostics)
    return {"events": events, "format": source_format, "diagnostics": diagnostics, "summary": _summarize(events)}


def normalize_event(record: dict[str, Any], *, line_number: int | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Normalize a single arbitrary log/span/metric object into a native event."""

    if not isinstance(record, dict):
        raise ContractLoadError("telemetry record must be a JSON object")

    # Already native: trust it, but still fill an inferred kind if missing.
    lowered = {str(key).lower(): key for key in record.keys()}
    diagnostics: list[dict[str, Any]] = []

    event: dict[str, Any] = {}
    if line_number is not None:
        event["_line"] = line_number

    consumed: set[str] = set()

    def take(aliases: list[str]) -> tuple[Any, str | None, list[str]]:
        found: list[tuple[str, Any]] = []
        for alias in aliases:
            original = lowered.get(alias)
            if original is not None and original not in consumed:
                found.append((original, record[original]))
        if not found:
            return None, None, []
        primary_key, primary_value = found[0]
        consumed.add(primary_key)
        extra_keys = [key for key, _ in found[1:]]
        return primary_value, primary_key, extra_keys

    def record_collision(canonical: str, primary_key: str | None, extra_keys: list[str], primary_value: Any) -> None:
        for extra in extra_keys:
            if record.get(extra) != primary_value:
                diagnostics.append(
                    {
                        "code": "adapter.alias_collision",
                        "message": f"multiple source keys map to '{canonical}': used '{primary_key}', also saw '{extra}'",
                        "line": line_number,
                        "canonical": canonical,
                    }
                )

    service, service_key, service_extra = take(_SERVICE_ALIASES)
    if isinstance(service, str) and service:
        event["service"] = service
        record_collision("service", service_key, service_extra, service)

    kind_value, _, _ = take(_KIND_ALIASES)
    severity, sev_key, sev_extra = take(_SEVERITY_ALIASES)
    message, _, _ = take(_MESSAGE_ALIASES)
    metric_value, _, _ = take(_VALUE_ALIASES)
    duration, _, _ = take(_DURATION_ALIASES)
    span_id, _, _ = take(_SPAN_ALIASES)
    trace_id, trace_key, trace_extra = take(_TRACE_ALIASES)
    request_id, _, _ = take(_REQUEST_ALIASES)
    name, _, _ = take(_NAME_ALIASES)

    ts_ms, _, _ = take(_TIMESTAMP_MS_ALIASES)
    ts_raw, _, _ = take(_TIMESTAMP_ALIASES)

    if span_id is not None:
        event["span_id"] = span_id
    if isinstance(trace_id, (str, int)) and str(trace_id):
        event["trace_id"] = trace_id
        record_collision("trace_id", trace_key, trace_extra, trace_id)
    if isinstance(request_id, (str, int)) and str(request_id):
        event["request_id"] = request_id

    timestamp_ms = _coerce_timestamp_ms(ts_ms, ts_raw)
    if timestamp_ms is not None:
        event["timestamp_ms"] = timestamp_ms

    kind, confidence, reason = _infer_kind(
        explicit=kind_value,
        severity=severity,
        message=message,
        metric_value=metric_value,
        duration=duration,
        span_id=span_id,
        trace_id=trace_id,
    )
    event["kind"] = kind
    event["_kind_confidence"] = confidence
    event["_kind_reason"] = reason

    if isinstance(name, str) and name:
        event["name"] = name
    elif kind == "log" and isinstance(message, str) and message:
        event["name"] = _log_name_from_message(message)
    elif isinstance(kind_value, str) and kind_value not in NATIVE_KINDS:
        event["name"] = kind_value

    if kind == "metric" and metric_value is not None:
        event["value"] = metric_value
    if kind == "log":
        if severity is not None:
            event["severity"] = _normalize_severity(severity)
        if isinstance(message, str):
            event["message"] = message

    # Everything we did not lift becomes an attribute, so nothing is dropped.
    attributes: dict[str, Any] = {}
    nested = record.get("attributes")
    if isinstance(nested, dict):
        attributes.update(nested)
    for container in ("tags", "fields"):
        nested = record.get(container)
        if isinstance(nested, dict):
            attributes.update(nested)
    for key, value in record.items():
        if key in _CONSUMED_TOP_LEVEL or key in consumed:
            continue
        if str(key).lower() in {"attributes", "tags", "fields"}:
            continue
        attributes.setdefault(key, value)
    if duration is not None and kind == "span":
        attributes.setdefault("duration_ms", duration)
    if attributes:
        event["attributes"] = attributes
    return event, diagnostics


def _parse_records(text: str, source: Path, *, tolerant: bool = False) -> tuple[list[dict[str, Any]], str, list[dict[str, Any]]]:
    diagnostics: list[dict[str, Any]] = []
    stripped = text.strip()
    if not stripped:
        return [], "json", diagnostics
    # OTLP exports are a single JSON object with resourceSpans/resourceLogs/etc.
    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict):
            if any(key in obj for key in ("resourceSpans", "resourceLogs", "resourceMetrics")):
                return [], "otlp", diagnostics
            return [obj], "json", diagnostics
    if stripped.startswith("["):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            if tolerant:
                diagnostics.append({"code": "adapter.unparsed_file", "message": f"could not parse JSON array: {exc}", "line": None})
                return [], "unknown", diagnostics
            raise ContractLoadError(f"{source} starts with '[' but is not valid JSON: {exc}") from exc
        if isinstance(data, list):
            if data and isinstance(data[0], dict) and any(key in data[0] for key in ("resourceSpans", "resourceLogs", "resourceMetrics")):
                return [], "otlp", diagnostics
            return [item for item in data if isinstance(item, dict)], "json-array", diagnostics
    records: list[dict[str, Any]] = []
    json_lines = 0
    logfmt_lines = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            record = None
        if isinstance(record, dict):
            records.append(record)
            json_lines += 1
            continue
        if record is not None:
            # Valid JSON but not an object (e.g. a bare number/string); skip.
            continue
        logfmt = parse_logfmt_line(line)
        if logfmt is not None:
            records.append(logfmt)
            logfmt_lines += 1
            continue
        if tolerant:
            diagnostics.append({"code": "adapter.unparsed_line", "message": "line is neither JSON nor logfmt; skipped", "line": line_number})
            continue
        raise ContractLoadError(f"line {line_number} of {source} is not JSON or logfmt; only JSON/JSONL/logfmt/OTLP telemetry is supported")
    if json_lines and logfmt_lines:
        fmt = "mixed"
    elif logfmt_lines:
        fmt = "logfmt"
    else:
        fmt = "jsonl"
    return records, fmt, diagnostics


# logfmt: ``key=value`` pairs, values optionally double-quoted. Common in Go
# services, Heroku, logrus, and many proxies/load balancers.
_LOGFMT_PAIR = re.compile(r'([A-Za-z_][\w.\-]*)=("(?:[^"\\]|\\.)*"|[^\s"]*)')
_LOGFMT_KNOWN_KEYS = {"level", "lvl", "severity", "msg", "message", "service", "time", "ts", "timestamp", "trace_id", "traceid", "span_id", "request_id", "status", "duration", "error", "logger"}


def parse_logfmt_line(line: str) -> dict[str, Any] | None:
    """Parse a logfmt line into a flat dict, or return None if it is not logfmt."""

    pairs: dict[str, Any] = {}
    matched_span = 0
    for match in _LOGFMT_PAIR.finditer(line):
        key = match.group(1)
        raw = match.group(2)
        pairs[key] = _logfmt_value(raw)
        matched_span += len(match.group(0))
    if not pairs:
        return None
    # Guard against accidental matches in prose ("a=b ...") by requiring either a
    # recognizable key or that key=value pairs dominate the line.
    has_known = any(key.lower() in _LOGFMT_KNOWN_KEYS for key in pairs)
    dense = len(pairs) >= 2 and matched_span >= 0.5 * len(line.strip())
    if has_known or dense:
        return pairs
    return None


def _logfmt_value(raw: str) -> Any:
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        inner = raw[1:-1]
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return inner.replace('\\"', '"').replace("\\\\", "\\")
    return _coerce_scalar(raw)


def _coerce_scalar(raw: str) -> Any:
    if raw == "":
        return ""
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "nil", "none"}:
        return None
    try:
        if raw.lstrip("-").isdigit():
            return int(raw)
        return float(raw)
    except ValueError:
        return raw


def _infer_kind(*, explicit: Any, severity: Any, message: Any, metric_value: Any, duration: Any, span_id: Any, trace_id: Any) -> tuple[str, str, str]:
    if isinstance(explicit, str):
        normalized = explicit.strip().lower()
        if normalized in NATIVE_KINDS:
            return normalized, "high", f"explicit kind '{explicit}'"
        if normalized in {"trace", "spans"}:
            return "span", "high", f"explicit kind '{explicit}'"
        if normalized in {"metrics", "gauge", "counter", "histogram"}:
            return "metric", "high", f"explicit kind '{explicit}'"
        if normalized in {"logs", "logentry", "event"}:
            return "log", "high", f"explicit kind '{explicit}'"
    # Severity/message are log-defining; trace_id/span_id are merely correlation
    # and can ride along on any signal, so they must not override a log verdict.
    if severity is not None or message is not None:
        return "log", "high", "severity/message present"
    if metric_value is not None and _is_number(metric_value):
        return "metric", "medium", "numeric value without log severity/message"
    if span_id is not None or duration is not None:
        return "span", "high", "span_id/duration present"
    if trace_id is not None:
        return "span", "low", "trace_id present without log markers"
    return "event", "low", "no distinguishing span/metric/log markers"


def _coerce_timestamp_ms(ts_ms: Any, ts_raw: Any) -> int | float | None:
    if _is_number(ts_ms):
        return ts_ms
    if _is_number(ts_raw):
        value = float(ts_raw)
        # Heuristic: seconds since epoch -> ms; leave small fixtures untouched.
        if 1_000_000_000 <= value < 1_000_000_000_000:
            return value * 1000.0
        return ts_raw
    if isinstance(ts_raw, str) and ts_raw.strip():
        parsed = _parse_iso8601_ms(ts_raw.strip())
        if parsed is not None:
            return parsed
    return None


def _parse_iso8601_ms(value: str) -> float | None:
    from datetime import datetime

    candidate = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return dt.timestamp() * 1000.0


def _normalize_severity(severity: Any) -> Any:
    if isinstance(severity, str):
        return severity.strip().upper()
    return severity


def _log_name_from_message(message: str) -> str:
    token = message.strip().split("\n", 1)[0]
    return token[:80] if token else "log"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    low_confidence = 0
    services: set[str] = set()
    for event in events:
        kind = str(event.get("kind", "event"))
        by_kind[kind] = by_kind.get(kind, 0) + 1
        if event.get("_kind_confidence") == "low":
            low_confidence += 1
        service = event.get("service")
        if isinstance(service, str) and service:
            services.add(service)
    return {
        "events": len(events),
        "by_kind": dict(sorted(by_kind.items())),
        "low_confidence_kind": low_confidence,
        "services": sorted(services),
    }
