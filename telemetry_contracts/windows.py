from __future__ import annotations

from collections import Counter
from typing import Any

from .findings import Finding, has_at_least
from .validator import _event_index, _event_timestamp_ms, _normalize_signal_kind, _safe_lookup, validate_events

WINDOW_MODEL: dict[str, Any] = {
    "name": "event-window-grouping-v1",
    "judgement": "T ⊨ C ⇓ F; group(T,F,K) ⇓ W",
    "relation": (
        "A finite validation run produces findings F, then assigns each event and event-local finding to every "
        "configured ownership window whose key is witnessed by the event. Findings without an event witness remain "
        "in a contract/global window so missing required evidence is not falsely attributed to an observed trace."
    ),
    "dimensions": {
        "trace": ["trace_id"],
        "request": ["request_id", "correlation_id"],
        "tenant": ["tenant_id", "tenant"],
        "deployment": ["deployment_id", "deployment", "environment", "env", "build_sha", "release"],
        "scenario": ["scenario_instance", "scenario_id", "scenario"],
        "incident": ["incident_id", "incident", "case_study"],
    },
}

DEFAULT_DIMENSIONS = ("trace", "request", "tenant", "deployment", "scenario", "incident")


def generate_event_window_report(
    contract: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    dimensions: list[str] | None = None,
    strict: bool | None = None,
    incident_slice_ms: int | None = None,
) -> dict[str, Any]:
    selected_dimensions = _normalize_dimensions(dimensions)
    findings = validate_events(contract, events, strict=strict)
    event_windows: dict[int, list[str]] = {}
    windows: dict[str, dict[str, Any]] = {}

    for position, event in enumerate(events):
        keys = _event_window_keys(event, selected_dimensions, incident_slice_ms)
        if not keys:
            keys = [_window_key("global", "all", "all")]
        event_windows[_event_index(event) or position] = keys
        for key in keys:
            window = windows.setdefault(key, _empty_window(key, event))
            _add_event(window, event)

    orphan_findings: list[dict[str, Any]] = []
    for finding in findings:
        finding_dict = finding.to_dict()
        attached = _attach_finding_to_event_windows(finding_dict, windows, event_windows)
        if not attached:
            matched_by_group = _attach_finding_by_group(finding_dict, windows)
            if not matched_by_group:
                orphan_findings.append(finding_dict)
                window = windows.setdefault("global:contract=all", _empty_window("global:contract=all", None))
                window["findings"].append(finding_dict)

    ordered_windows = sorted(windows.values(), key=lambda item: (-item["summary"]["finding_count"], item["id"]))
    for window in ordered_windows:
        _finalize_window(window)
    summary = {
        "pass": not has_at_least(findings, "error"),
        "events": len(events),
        "findings": len(findings),
        "windows": len(ordered_windows),
        "windows_with_findings": sum(1 for window in ordered_windows if window["summary"]["finding_count"]),
        "orphan_findings": len(orphan_findings),
        "dimensions": selected_dimensions,
        "incident_slice_ms": incident_slice_ms,
        "findings_by_code": dict(sorted(Counter(finding.code for finding in findings).items())),
    }
    return {
        "model": WINDOW_MODEL,
        "service": contract.get("service", ""),
        "summary": summary,
        "windows": ordered_windows,
        "orphan_findings": orphan_findings,
        "findings": [finding.to_dict() for finding in findings],
    }


def format_event_window_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Event-window report",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Service: `{report.get('service', '')}`",
        f"- Judgement: `{report['model']['judgement']}`",
        f"- Pass: `{summary['pass']}`",
        f"- Events: {summary['events']}",
        f"- Findings: {summary['findings']}",
        f"- Windows: {summary['windows']} ({summary['windows_with_findings']} with findings)",
        f"- Dimensions: {', '.join(summary['dimensions'])}",
    ]
    if summary.get("incident_slice_ms") is not None:
        lines.append(f"- Incident slice: {summary['incident_slice_ms']} ms")
    if summary.get("findings_by_code"):
        lines.extend(["", "## Findings by code", ""])
        for code, count in summary["findings_by_code"].items():
            lines.append(f"- `{code}`: {count}")
    lines.extend(["", "## Windows", ""])
    for window in report["windows"]:
        wsummary = window["summary"]
        if not wsummary["finding_count"]:
            continue
        lines.append(f"### `{window['id']}`")
        lines.append("")
        lines.append(f"- Dimension: `{window['dimension']}`")
        lines.append(f"- Event count: {wsummary['event_count']}")
        lines.append(f"- Finding count: {wsummary['finding_count']}")
        if window.get("services"):
            lines.append(f"- Services: {', '.join(window['services'])}")
        if window.get("time_range_ms"):
            lines.append(f"- Time range ms: {window['time_range_ms'][0]}..{window['time_range_ms'][1]}")
        if wsummary.get("finding_codes"):
            lines.append(f"- Codes: {', '.join(f'`{code}`={count}' for code, count in wsummary['finding_codes'].items())}")
        for finding in window["findings"][:5]:
            lines.append(f"  - {finding['severity']} `{finding['code']}` at `{finding.get('path', '')}`: {finding['message']}")
        lines.append("")
    if summary["orphan_findings"]:
        lines.extend(["## Contract/global findings", ""])
        for finding in report.get("orphan_findings", []):
            lines.append(f"- {finding['severity']} `{finding['code']}`: {finding['message']}")
    return "\n".join(lines).rstrip()


def _normalize_dimensions(dimensions: list[str] | None) -> list[str]:
    raw = dimensions or list(DEFAULT_DIMENSIONS)
    result: list[str] = []
    for dimension in raw:
        if dimension == "all":
            for item in DEFAULT_DIMENSIONS:
                if item not in result:
                    result.append(item)
            continue
        if dimension not in WINDOW_MODEL["dimensions"]:
            raise ValueError(f"unknown event-window dimension {dimension!r}; choose one of {sorted(WINDOW_MODEL['dimensions'])}")
        if dimension not in result:
            result.append(dimension)
    return result


def _event_window_keys(event: dict[str, Any], dimensions: list[str], incident_slice_ms: int | None) -> list[str]:
    keys: list[str] = []
    for dimension in dimensions:
        for field_name in WINDOW_MODEL["dimensions"][dimension]:
            value = _safe_lookup(event, field_name)
            if value not in (None, ""):
                keys.append(_window_key(dimension, field_name, value))
                break
    if incident_slice_ms is not None:
        if incident_slice_ms <= 0:
            raise ValueError("incident_slice_ms must be positive")
        timestamp = _event_timestamp_ms(event)
        if timestamp is not None:
            keys.append(_window_key("incident", "slice_ms", int(timestamp // incident_slice_ms) * incident_slice_ms))
    return keys


def _window_key(dimension: str, field_name: str, value: Any) -> str:
    return f"{dimension}:{field_name}={value}"


def _empty_window(key: str, event: dict[str, Any] | None) -> dict[str, Any]:
    dimension, rest = key.split(":", 1) if ":" in key else ("global", key)
    field_name, value = rest.split("=", 1) if "=" in rest else ("key", rest)
    return {
        "id": key,
        "dimension": dimension,
        "field": field_name,
        "value": value,
        "events": [],
        "findings": [],
        "services": [],
        "time_range_ms": None,
        "summary": {"event_count": 0, "finding_count": 0, "finding_codes": {}},
    }


def _add_event(window: dict[str, Any], event: dict[str, Any]) -> None:
    event_index = _event_index(event)
    timestamp = _event_timestamp_ms(event)
    event_summary = {
        "event_index": event_index,
        "kind": _normalize_signal_kind(event.get("kind")),
        "name": event.get("name"),
        "service": event.get("service"),
        "timestamp_ms": timestamp,
    }
    if event_summary not in window["events"]:
        window["events"].append(event_summary)
    if isinstance(event.get("service"), str) and event["service"] not in window["services"]:
        window["services"].append(event["service"])
    if timestamp is not None:
        if window["time_range_ms"] is None:
            window["time_range_ms"] = [timestamp, timestamp]
        else:
            window["time_range_ms"][0] = min(window["time_range_ms"][0], timestamp)
            window["time_range_ms"][1] = max(window["time_range_ms"][1], timestamp)


def _attach_finding_to_event_windows(finding: dict[str, Any], windows: dict[str, dict[str, Any]], event_windows: dict[int, list[str]]) -> bool:
    event_index = finding.get("event_index")
    if not isinstance(event_index, int):
        return False
    keys = event_windows.get(event_index, [])
    for key in keys:
        windows[key]["findings"].append(finding)
    return bool(keys)


def _attach_finding_by_group(finding: dict[str, Any], windows: dict[str, dict[str, Any]]) -> bool:
    details = finding.get("details")
    group = details.get("group") if isinstance(details, dict) else None
    if not isinstance(group, (list, tuple)) or not group:
        return False
    group_values = {str(item) for item in group if item not in (None, "")}
    attached = False
    for window in windows.values():
        if str(window.get("value")) in group_values:
            window["findings"].append(finding)
            attached = True
    return attached


def _finalize_window(window: dict[str, Any]) -> None:
    codes = Counter(str(finding["code"]) for finding in window["findings"])
    window["events"] = sorted(window["events"], key=lambda item: (item["timestamp_ms"] is None, item["timestamp_ms"] or 0, item["event_index"] or 0))
    window["services"] = sorted(window["services"])
    window["summary"] = {
        "event_count": len(window["events"]),
        "finding_count": len(window["findings"]),
        "finding_codes": dict(sorted(codes.items())),
    }
