from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from importlib import metadata
from pathlib import Path
from typing import Any


def run_doctor(collector_exports: list[str] | None = None, report_paths: list[str] | None = None) -> dict[str, Any]:
    checks = [
        _check_python_version(),
        _check_yaml_support(),
        _check_package_install(),
        _check_ci_environment(),
    ]
    checks.extend(_check_paths("collector_export", collector_exports or [], should_exist=True))
    checks.extend(_check_paths("report_path", report_paths or [], should_exist=False))
    counts = {"ok": 0, "warning": 0, "error": 0}
    for check in checks:
        counts[check["status"]] += 1
    return {
        "tool": "telemetry-contracts-doctor-v1",
        "summary": {"pass": counts["error"] == 0, **counts},
        "checks": checks,
        "limitations": [
            "Doctor validates local CLI assumptions and file paths only; it does not inspect private collector backends.",
            "YAML support is optional because JSON contracts are the deterministic baseline.",
        ],
    }


def format_doctor_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# telemetry-contracts doctor",
        "",
        f"- Pass: `{str(report['summary']['pass']).lower()}`",
        f"- OK: {report['summary']['ok']}",
        f"- Warnings: {report['summary']['warning']}",
        f"- Errors: {report['summary']['error']}",
        "",
        "| Check | Status | Message | Details |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['name']} | `{check['status']}` | {check['message']} | `{json.dumps(check.get('details', {}), sort_keys=True)}` |")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.get("limitations", []))
    lines.append("")
    return "\n".join(lines)


def _check_python_version() -> dict[str, Any]:
    ok = sys.version_info >= (3, 10)
    return {
        "name": "python_version",
        "status": "ok" if ok else "error",
        "message": "Python version satisfies >=3.10" if ok else "Python >=3.10 is required",
        "details": {"version": platform.python_version(), "executable": Path(sys.executable).name},
    }


def _check_yaml_support() -> dict[str, Any]:
    available = importlib.util.find_spec("yaml") is not None
    return {
        "name": "optional_yaml_support",
        "status": "ok" if available else "warning",
        "message": "PyYAML is importable" if available else "PyYAML is not installed; JSON contracts still work",
        "details": {"available": available},
    }


def _check_package_install() -> dict[str, Any]:
    try:
        version = metadata.version("telemetry-contracts")
        return {"name": "package_install", "status": "ok", "message": "telemetry-contracts package metadata is installed", "details": {"version": version}}
    except metadata.PackageNotFoundError:
        source_tree = (Path.cwd() / "telemetry_contracts").exists()
        return {"name": "package_install", "status": "warning", "message": "package metadata not found; running from source tree is supported", "details": {"source_tree": source_tree}}


def _check_ci_environment() -> dict[str, Any]:
    ci_vars = {key: os.environ.get(key) for key in ("CI", "GITHUB_ACTIONS", "GITHUB_WORKFLOW", "GITHUB_SHA") if os.environ.get(key)}
    return {
        "name": "ci_environment",
        "status": "ok" if ci_vars else "warning",
        "message": "CI environment variables detected" if ci_vars else "No CI environment variables detected; local runs are still valid",
        "details": ci_vars,
    }


def _check_paths(name: str, paths: list[str], should_exist: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for raw in paths:
        path = Path(raw)
        exists = path.exists()
        parent_exists = path.parent.exists() if path.parent != Path("") else True
        ok = exists if should_exist else parent_exists
        checks.append({
            "name": name,
            "status": "ok" if ok else "error",
            "message": f"{raw} {'exists' if exists else 'does not exist'}" if should_exist else f"parent for {raw} {'exists' if parent_exists else 'does not exist'}",
            "details": {"path": raw, "exists": exists, "parent_exists": parent_exists},
        })
    return checks
