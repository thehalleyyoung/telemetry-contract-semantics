from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .findings import Finding


LEGACY_ATTRIBUTE_REMEDIATIONS: dict[str, dict[str, str]] = {
    "http.method": {
        "expected": "http.request.method",
        "convention": "OpenTelemetry HTTP semantic conventions use http.request.method for request methods.",
    },
    "http.status_code": {
        "expected": "http.response.status_code",
        "convention": "OpenTelemetry HTTP semantic conventions use http.response.status_code for response status.",
    },
    "http.url": {
        "expected": "url.full",
        "convention": "OpenTelemetry URL semantic conventions use url.full; avoid query strings when they carry sensitive data.",
    },
    "net.peer.name": {
        "expected": "server.address",
        "convention": "OpenTelemetry network/server conventions use server.address for the remote server name.",
    },
    "db.system": {
        "expected": "db.system.name",
        "convention": "OpenTelemetry database semantic conventions identify the database system with db.system.name.",
    },
    "db.statement": {
        "expected": "db.query.text",
        "convention": "OpenTelemetry database semantic conventions use db.query.text for query text when it is safe to emit.",
    },
    "db.operation": {
        "expected": "db.operation.name",
        "convention": "OpenTelemetry database semantic conventions use db.operation.name for the database operation.",
    },
    "messaging.destination": {
        "expected": "messaging.destination.name",
        "convention": "OpenTelemetry messaging semantic conventions use messaging.destination.name for destination names.",
    },
    "messaging.operation": {
        "expected": "messaging.operation.name",
        "convention": "OpenTelemetry messaging semantic conventions use messaging.operation.name for messaging operations.",
    },
}


def lint_semantic_conventions(contract: dict[str, Any], events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Lint contracts and optional events against bounded OTel/local naming policies."""

    event_list = events or []
    findings: list[Finding] = []
    findings.extend(_lint_contract_signals(contract))
    findings.extend(_lint_events(contract, event_list))
    finding_dicts = [finding.to_dict() for finding in findings]
    return {
        "semantics": "SEMCONV-T ⊨ naming_and_attribute_policy iff every declared/observed signal satisfies cited OpenTelemetry semantic-convention or local-policy obligations.",
        "policy_sources": [
            "OpenTelemetry HTTP semantic conventions: request/response attributes such as http.request.method, http.route, and http.response.status_code.",
            "OpenTelemetry database semantic conventions: database attributes such as db.system.name, db.operation.name, db.namespace, db.collection.name, server.address, and db.query.text.",
            "OpenTelemetry messaging semantic conventions: messaging.system, messaging.destination.name, and messaging.operation.name.",
            "OpenTelemetry metrics guidance: declare measurement units separately from metric identity when possible.",
            "Contract metadata.semantic_conventions local policy entries checked as artifact-scoped extensions.",
        ],
        "summary": {
            "pass": not any(item.severity == "error" for item in findings),
            "contracts_checked": 1,
            "events_checked": len(event_list),
            "findings": len(findings),
            "findings_by_code": dict(sorted(Counter(item.code for item in findings).items())),
            "findings_by_severity": dict(sorted(Counter(item.severity for item in findings).items())),
        },
        "findings": finding_dicts,
    }


def format_semconv_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Semantic-convention lint report",
        "",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Events checked: {summary['events_checked']}",
        f"- Findings: {summary['findings']}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        f"- Findings by severity: `{json.dumps(summary['findings_by_severity'], sort_keys=True)}`",
        "",
        "## Policy sources",
    ]
    lines.extend(f"- {source}" for source in report.get("policy_sources", []))
    lines.extend(["", "## Findings"])
    if not report.get("findings"):
        lines.append("No semantic-convention findings.")
        return "\n".join(lines)
    lines.append("| Severity | Code | Location | Remediation | Convention/local policy |")
    lines.append("| --- | --- | --- | --- | --- |")
    for finding in report["findings"]:
        details = finding.get("details", {}) or {}
        remediation = details.get("remediation") or finding.get("remediation", "")
        convention = details.get("convention") or details.get("policy", "")
        lines.append(
            f"| {finding['severity']} | `{finding['code']}` | `{finding['path']}` | "
            f"{_escape_table(str(remediation))} | {_escape_table(str(convention))} |"
        )
    lines.append("")
    return "\n".join(lines)


def _lint_contract_signals(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        raw = contract.get(section, []) or []
        if not isinstance(raw, list):
            continue
        for index, spec in enumerate(raw):
            if not isinstance(spec, dict):
                continue
            signal_path = f"$.{section}[{index}]"
            name = spec.get("name")
            if not isinstance(name, str):
                continue
            fields = _declared_fields(spec)
            findings.extend(_legacy_attribute_findings(fields, f"{signal_path}.fields", "contract"))
            findings.extend(_domain_required_contract_findings(kind, name, fields, spec, signal_path))
            if kind == "metric":
                findings.extend(_metric_unit_findings(name, spec, signal_path))
    findings.extend(_local_policy_contract_findings(contract))
    return findings


def _lint_events(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    for event in events:
        kind = _normalize_kind(event.get("kind"))
        name = event.get("name")
        if kind not in {"span", "metric", "log"} or not isinstance(name, str):
            continue
        fields = _event_fields(event)
        path = f"event[{_event_index(event)}]"
        findings.extend(_legacy_attribute_findings(fields, path, "event", event))
        findings.extend(_domain_required_event_findings(kind, name, fields, event, path))
    findings.extend(_local_policy_event_findings(contract, events))
    return findings


def _legacy_attribute_findings(fields: set[str], path: str, scope: str, event: dict[str, Any] | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for field in sorted(fields):
        rule = LEGACY_ATTRIBUTE_REMEDIATIONS.get(field)
        if not rule:
            continue
        findings.append(
            Finding(
                "warning",
                "semconv.legacy_attribute",
                f"{scope} uses legacy semantic attribute '{field}'; use '{rule['expected']}'",
                f"{path}.{field}",
                None,
                _event_index(event) if event else None,
                {
                    "attribute": field,
                    "expected_attribute": rule["expected"],
                    "convention": rule["convention"],
                    "remediation": f"Rename '{field}' to '{rule['expected']}' in the contract and emitted telemetry.",
                },
            )
        )
    return findings


def _domain_required_contract_findings(kind: str, name: str, fields: set[str], spec: dict[str, Any], path: str) -> list[Finding]:
    findings: list[Finding] = []
    for attribute, convention in _required_attributes(kind, name, fields):
        if attribute not in fields:
            findings.append(
                Finding(
                    "warning",
                    "semconv.missing_attribute",
                    f"{kind} '{name}' should declare semantic attribute '{attribute}'",
                    f"{path}.fields.{attribute}",
                    path,
                    None,
                    {
                        "kind": kind,
                        "name": name,
                        "attribute": attribute,
                        "convention": convention,
                        "remediation": f"Add '{attribute}' to the contract and emit it on '{name}'.",
                    },
                )
            )
    if kind == "span" and _looks_http(name, fields) and "http.route" in fields and not _http_span_name_matches(name):
        findings.append(
            Finding(
                "warning",
                "semconv.signal_name",
                f"HTTP span '{name}' should use the low-cardinality '{METHOD} {http.route}' naming shape",
                f"{path}.name",
                path,
                None,
                {
                    "convention": "OpenTelemetry HTTP span names should be low-cardinality route templates.",
                    "remediation": "Use a template such as 'GET /checkout/{cart_id}' and keep raw URLs in redacted attributes only when needed.",
                },
            )
        )
    return findings


def _domain_required_event_findings(kind: str, name: str, fields: set[str], event: dict[str, Any], path: str) -> list[Finding]:
    findings: list[Finding] = []
    for attribute, convention in _required_attributes(kind, name, fields):
        if attribute not in fields:
            findings.append(
                Finding(
                    "warning",
                    "semconv.missing_attribute",
                    f"{kind} '{name}' should emit semantic attribute '{attribute}'",
                    f"{path}.{attribute}",
                    None,
                    _event_index(event),
                    {
                        "kind": kind,
                        "name": name,
                        "attribute": attribute,
                        "convention": convention,
                        "remediation": f"Emit '{attribute}' on '{name}' or document a local policy exception.",
                    },
                )
            )
    return findings


def _required_attributes(kind: str, name: str, fields: set[str]) -> list[tuple[str, str]]:
    rules: list[tuple[str, str]] = []
    if _looks_http(name, fields):
        rules.extend(
            [
                ("http.request.method", "OpenTelemetry HTTP semantic conventions identify the request method with http.request.method."),
                ("http.route", "OpenTelemetry HTTP server spans use http.route for low-cardinality route templates."),
                ("http.response.status_code", "OpenTelemetry HTTP semantic conventions identify response status with http.response.status_code."),
            ]
        )
    if _looks_database(name, fields):
        rules.append(("db.system.name", "OpenTelemetry database semantic conventions identify database technology with db.system.name."))
        if kind == "span":
            rules.append(("db.operation.name", "OpenTelemetry database spans identify the database operation with db.operation.name."))
    if _looks_messaging(name, fields):
        rules.extend(
            [
                ("messaging.system", "OpenTelemetry messaging semantic conventions identify the broker/system with messaging.system."),
                ("messaging.destination.name", "OpenTelemetry messaging semantic conventions identify queues/topics with messaging.destination.name."),
                ("messaging.operation.name", "OpenTelemetry messaging semantic conventions identify publish, receive, or process with messaging.operation.name."),
            ]
        )
    return rules


def _metric_unit_findings(name: str, spec: dict[str, Any], path: str) -> list[Finding]:
    unit_suffixes = {"_ms": "ms", "_bytes": "By", "_seconds": "s"}
    for suffix, unit in unit_suffixes.items():
        if not name.endswith(suffix):
            continue
        value_spec = spec.get("value") if isinstance(spec.get("value"), dict) else {}
        if value_spec.get("unit"):
            return []
        expected_name = name[: -len(suffix)]
        return [
            Finding(
                "warning",
                "semconv.metric_unit",
                f"metric '{name}' encodes unit suffix '{suffix}' without declaring value.unit",
                f"{path}.value.unit",
                path,
                None,
                {
                    "metric": name,
                    "expected_name": expected_name,
                    "expected_unit": unit,
                    "convention": "OpenTelemetry metric semantic conventions prefer explicit units in instrument metadata over unit-only name suffixes.",
                    "remediation": f"Declare value.unit '{unit}' and consider renaming the metric to '{expected_name}'.",
                },
            )
        ]
    return []


def _local_policy_contract_findings(contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    for index, policy in enumerate(_required_local_attributes(contract)):
        path = f"$.metadata.semantic_conventions.required_attributes[{index}]"
        section = {"span": "spans", "metric": "metrics", "log": "logs"}.get(policy["kind"], "")
        spec = _find_signal_spec(contract, section, policy["name"]) if section else None
        if spec is None:
            continue
        if policy["attribute"] not in _declared_fields(spec):
            findings.append(
                Finding(
                    policy["severity"],
                    "semconv.local_policy",
                    f"{policy['kind']} '{policy['name']}' must declare local semantic attribute '{policy['attribute']}'",
                    f"{path}.attribute",
                    path,
                    None,
                    {
                        "kind": policy["kind"],
                        "name": policy["name"],
                        "attribute": policy["attribute"],
                        "convention": policy["convention"],
                        "remediation": policy["remediation"],
                        "expected_value": policy.get("expected_value"),
                    },
                )
            )
    return findings


def _local_policy_event_findings(contract: dict[str, Any], events: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    for policy in _required_local_attributes(contract):
        for event in events:
            if _normalize_kind(event.get("kind")) != policy["kind"] or event.get("name") != policy["name"]:
                continue
            fields = _event_field_values(event)
            if policy["attribute"] not in fields:
                findings.append(
                    Finding(
                        policy["severity"],
                        "semconv.local_policy",
                        f"{policy['kind']} '{policy['name']}' missing local semantic attribute '{policy['attribute']}'",
                        f"event[{_event_index(event)}].{policy['attribute']}",
                        "$.metadata.semantic_conventions.required_attributes",
                        _event_index(event),
                        {
                            "kind": policy["kind"],
                            "name": policy["name"],
                            "attribute": policy["attribute"],
                            "convention": policy["convention"],
                            "remediation": policy["remediation"],
                            "expected_value": policy.get("expected_value"),
                        },
                    )
                )
                continue
            if "expected_value" in policy and fields.get(policy["attribute"]) != policy["expected_value"]:
                findings.append(
                    Finding(
                        policy["severity"],
                        "semconv.local_policy",
                        f"{policy['kind']} '{policy['name']}' has {policy['attribute']}={fields.get(policy['attribute'])!r}, expected {policy['expected_value']!r}",
                        f"event[{_event_index(event)}].{policy['attribute']}",
                        "$.metadata.semantic_conventions.required_attributes",
                        _event_index(event),
                        {
                            "kind": policy["kind"],
                            "name": policy["name"],
                            "attribute": policy["attribute"],
                            "convention": policy["convention"],
                            "remediation": policy["remediation"],
                            "expected_value": policy.get("expected_value"),
                        },
                    )
                )
    return findings


def _required_local_attributes(contract: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = contract.get("metadata")
    semconv = metadata.get("semantic_conventions") if isinstance(metadata, dict) else None
    if not isinstance(semconv, dict):
        return []
    raw = semconv.get("required_attributes", []) or []
    if not isinstance(raw, list):
        return []
    policies: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind = _normalize_kind(item.get("kind", item.get("signal")))
        name = item.get("name")
        attribute = item.get("attribute", item.get("field"))
        if kind not in {"span", "metric", "log"} or not isinstance(name, str) or not isinstance(attribute, str):
            continue
        convention = item.get("convention") if isinstance(item.get("convention"), str) else "Local semantic-convention policy."
        remediation = item.get("remediation") if isinstance(item.get("remediation"), str) else f"Emit '{attribute}' on '{name}'."
        policies.append(
            {
                "kind": kind,
                "name": name,
                "attribute": attribute,
                "expected_value": item.get("expected_value"),
                "severity": item.get("severity") if item.get("severity") in {"info", "warning", "error"} else "warning",
                "convention": convention,
                "remediation": remediation,
            }
        )
    return policies


def _declared_fields(spec: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    for container in ("fields", "attributes", "tags"):
        raw = spec.get(container)
        if isinstance(raw, dict):
            fields.update(str(key) for key in raw)
    if isinstance(spec.get("value"), dict):
        fields.add("value")
    return fields


def _event_fields(event: dict[str, Any]) -> set[str]:
    return set(_event_field_values(event))


def _event_field_values(event: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in ("trace_id", "span_id", "parent_span_id", "timestamp_ms", "severity", "value"):
        if key in event:
            values[key] = event[key]
    for container in ("attributes", "tags", "fields", "resource", "scope"):
        raw = event.get(container)
        if isinstance(raw, dict):
            values.update({str(key): value for key, value in raw.items()})
    return values


def _find_signal_spec(contract: dict[str, Any], section: str, name: str) -> dict[str, Any] | None:
    raw = contract.get(section, []) or []
    if not isinstance(raw, list):
        return None
    return next((item for item in raw if isinstance(item, dict) and item.get("name") == name), None)


def _looks_http(name: str, fields: set[str]) -> bool:
    lowered = name.lower()
    return lowered.startswith("http.") or lowered.startswith("http ") or any(field.startswith("http.") or field.startswith("url.") for field in fields)


def _looks_database(name: str, fields: set[str]) -> bool:
    lowered = name.lower()
    return (
        lowered.startswith(("db.", "database.", "postgres.", "mysql.", "sql."))
        or "postgres" in lowered
        or any(field.startswith("db.") for field in fields)
    )


def _looks_messaging(name: str, fields: set[str]) -> bool:
    lowered = name.lower()
    return lowered.startswith(("messaging.", "queue.", "kafka.", "rabbitmq.")) or any(field.startswith("messaging.") for field in fields)


def _http_span_name_matches(name: str) -> bool:
    parts = name.split(maxsplit=1)
    return len(parts) == 2 and parts[0].isupper() and parts[1].startswith("/")


def _normalize_kind(value: Any) -> str:
    raw = str(value or "").lower()
    return {"spans": "span", "logs": "log", "metrics": "metric"}.get(raw, raw)


def _event_index(event: dict[str, Any] | None) -> int | None:
    if event is None:
        return None
    line = event.get("_line")
    return line if isinstance(line, int) else None


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")
