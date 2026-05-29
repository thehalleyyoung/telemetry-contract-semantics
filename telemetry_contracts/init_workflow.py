from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .incident_report import generate_incident_readiness_report, format_incident_readiness_markdown


def scaffold_project(service: str, owner: str, output_dir: str | Path, *, force: bool = False) -> dict[str, Any]:
    root = Path(output_dir)
    if root.exists() and any(root.iterdir()) and not force:
        raise FileExistsError(f"output directory is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    contract = _contract(service, owner)
    events = _events(service)
    files = {
        "contract": root / "contract.json",
        "events": root / "events.jsonl",
        "owner_metadata": root / "owner_metadata.json",
        "ci_gate": root / "ci-telemetry-contracts.sh",
        "incident_readiness_json": root / "incident_readiness.json",
        "incident_readiness_markdown": root / "incident_readiness.md",
    }
    files["contract"].write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["events"].write_text("\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n", encoding="utf-8")
    metadata = {"service": service, "owner": owner, "generated_by": "telemetry-contracts init", "responsible_handling": "Review fields before using with production telemetry; do not commit secrets."}
    files["owner_metadata"].write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["ci_gate"].write_text(_ci_script(), encoding="utf-8")
    files["ci_gate"].chmod(0o755)
    report = generate_incident_readiness_report(contract, events, ["baseline-readiness"])
    files["incident_readiness_json"].write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    files["incident_readiness_markdown"].write_text(format_incident_readiness_markdown(report), encoding="utf-8")
    return {"service": service, "owner": owner, "output_dir": str(root), "files": {key: str(path) for key, path in files.items()}, "incident_readiness_score": report["summary"]["incident_readiness_score"]}


def _contract(service: str, owner: str) -> dict[str, Any]:
    return {
        "version": "1.0",
        "service": service,
        "metadata": {"owner": owner, "retention": {"traces_days": 7, "metrics_days": 30, "logs_days": 14}},
        "correlation": {"keys": ["trace_id", "request_id"], "require_on": ["spans", "logs", "metrics"]},
        "spans": [{"name": f"{service}.request", "required": True, "fields": {"tenant_id": {"type": "string", "required": True}, "result": {"type": "string", "required": True, "allowed_values": ["ok", "error"]}, "duration_ms": {"type": "number", "required": True, "min": 0, "unit": "ms"}}}],
        "metrics": [{"name": f"{service}.requests.total", "required": True, "value": {"type": "number", "min": 0, "unit": "count"}, "tags": {"tenant_id": {"type": "string", "required": True}, "result": {"type": "string", "required": True}}}],
        "logs": [{"name": f"{service}.error", "required": True, "severity": "ERROR", "message_pattern": "request failed", "fields": {"tenant_id": {"type": "string", "required": True}, "error_code": {"type": "string", "required": True}, "remediation_hint": {"type": "string", "required": True}}}],
        "static_expectations": {"spans": [f"{service}.request"], "metrics": [f"{service}.requests.total"], "logs": [f"{service}.error"]},
        "scenarios": [{"id": "baseline-readiness", "question": "Can the owner identify tenant, outcome, latency, error code, and remediation for a failed request?", "minimum_observations": [{"signal": "span", "name": f"{service}.request", "fields": ["tenant_id", "result", "duration_ms"]}, {"signal": "log", "name": f"{service}.error", "fields": ["tenant_id", "error_code", "remediation_hint"]}, {"signal": "metric", "name": f"{service}.requests.total", "fields": ["tenant_id", "result"]}]}],
    }


def _events(service: str) -> list[dict[str, Any]]:
    return [
        {"kind": "span", "name": f"{service}.request", "timestamp": 1, "trace_id": "trace-init-1", "request_id": "req-init-1", "attributes": {"tenant_id": "tenant-example", "result": "error", "duration_ms": 42}},
        {"kind": "metric", "name": f"{service}.requests.total", "timestamp": 2, "trace_id": "trace-init-1", "request_id": "req-init-1", "value": 1, "tags": {"tenant_id": "tenant-example", "result": "error"}},
        {"kind": "log", "name": f"{service}.error", "timestamp": 3, "trace_id": "trace-init-1", "request_id": "req-init-1", "severity": "ERROR", "message": "request failed", "fields": {"tenant_id": "tenant-example", "error_code": "E_INIT", "remediation_hint": "replace scaffold values with service-specific guidance"}},
    ]


def _ci_script() -> str:
    return """#!/usr/bin/env sh
set -eu
python3 -m telemetry_contracts.cli lint-contract --contract contract.json
python3 -m telemetry_contracts.cli validate --contract contract.json --events events.jsonl
python3 -m telemetry_contracts.cli report incident-readiness --contract contract.json --events events.jsonl --format markdown --output incident_readiness.md
"""
