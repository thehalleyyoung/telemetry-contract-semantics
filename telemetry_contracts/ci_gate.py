from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .sarif import extract_findings

SEVERITY_RANK = {"info": 1, "warning": 2, "error": 3}


def evaluate_ci_gate(findings_report: str | Path, baseline_path: str | Path | None = None, *, fail_on: str = "error", today: date | None = None) -> dict[str, Any]:
    report = json.loads(Path(findings_report).read_text(encoding="utf-8"))
    findings = extract_findings(report)
    baseline = _load_baseline(baseline_path)
    today = today or date.today()
    active_baselines: list[dict[str, Any]] = []
    expired_baselines: list[dict[str, Any]] = []
    for item in baseline:
        expires = _parse_date(item.get("expires_at"))
        if expires is not None and expires < today:
            expired_baselines.append(item)
        else:
            active_baselines.append(item)
    threshold = SEVERITY_RANK[fail_on]
    blocking: list[dict[str, Any]] = []
    baselined: list[dict[str, Any]] = []
    for finding in findings:
        if SEVERITY_RANK.get(str(finding.get("severity")), 3) < threshold:
            continue
        match = next((item for item in active_baselines if _matches(finding, item)), None)
        if match:
            copied = dict(finding)
            copied["baseline_owner"] = match.get("owner")
            copied["baseline_expires_at"] = match.get("expires_at")
            baselined.append(copied)
        else:
            blocking.append(finding)
    return {
        "summary": {
            "findings": len(findings),
            "threshold": fail_on,
            "baselined": len(baselined),
            "blocking": len(blocking),
            "expired_baselines": len(expired_baselines),
            "pass": not blocking and not expired_baselines,
        },
        "blocking_findings": blocking,
        "baselined_findings": baselined,
        "expired_baselines": expired_baselines,
    }


def format_ci_gate_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Telemetry contracts CI gate",
        "",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Threshold: `{summary['threshold']}`",
        f"- Findings inspected: {summary['findings']}",
        f"- Baselined findings: {summary['baselined']}",
        f"- Blocking findings: {summary['blocking']}",
        f"- Expired baselines: {summary['expired_baselines']}",
        "",
    ]
    if report.get("blocking_findings"):
        lines.extend(["## Blocking findings", "", "| Code | Severity | Path | Message |", "| --- | --- | --- | --- |"])
        for item in report["blocking_findings"]:
            lines.append(f"| {item.get('code')} | {item.get('severity')} | `{item.get('path')}` | {item.get('message')} |")
        lines.append("")
    if report.get("expired_baselines"):
        lines.extend(["## Expired baselines", "", "| Code | Path | Owner | Expired |", "| --- | --- | --- | --- |"])
        for item in report["expired_baselines"]:
            lines.append(f"| {item.get('code')} | `{item.get('path') or item.get('path_suffix')}` | {item.get('owner')} | {item.get('expires_at')} |")
        lines.append("")
    return "\n".join(lines)


def _load_baseline(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("findings", data if isinstance(data, list) else []) if isinstance(data, (dict, list)) else []
    return [item for item in items if isinstance(item, dict)]


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value).date()


def _matches(finding: dict[str, Any], baseline: dict[str, Any]) -> bool:
    if baseline.get("code") and finding.get("code") != baseline.get("code"):
        return False
    for key in ("path", "contract_path", "event_index"):
        if key in baseline and baseline[key] != finding.get(key):
            return False
    suffix = baseline.get("path_suffix")
    if suffix and not str(finding.get("path", "")).endswith(str(suffix)):
        return False
    return True
