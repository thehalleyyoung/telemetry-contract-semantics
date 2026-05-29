from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .findings import TAXONOMY


def findings_to_sarif(findings: list[dict[str, Any]], *, tool_name: str = "telemetry-contracts") -> dict[str, Any]:
    rules = {str(item.get("code")): _rule(str(item.get("code"))) for item in findings if item.get("code")}
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {"driver": {"name": tool_name, "informationUri": "https://github.com/thehalleyyoung/telemetry-contract-semantics", "rules": [rules[key] for key in sorted(rules)]}},
                "results": [_result(item) for item in findings],
            }
        ],
    }


def report_to_sarif(report: dict[str, Any], *, tool_name: str = "telemetry-contracts") -> dict[str, Any]:
    return findings_to_sarif(extract_findings(report), tool_name=tool_name)


def extract_findings(report: Any) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if isinstance(report, dict):
        direct = report.get("findings")
        if isinstance(direct, list):
            findings.extend(item for item in direct if isinstance(item, dict))
        for case in report.get("cases", []) if isinstance(report.get("cases"), list) else []:
            if isinstance(case, dict) and isinstance(case.get("findings"), list):
                for item in case["findings"]:
                    if isinstance(item, dict):
                        copied = dict(item)
                        copied.setdefault("case_id", case.get("id"))
                        findings.append(copied)
    return findings


def _rule(code: str) -> dict[str, Any]:
    meta = TAXONOMY.get(code, {})
    return {
        "id": code,
        "name": code,
        "shortDescription": {"text": code},
        "fullDescription": {"text": str(meta.get("formal_clause", code))},
        "help": {"text": str(meta.get("remediation", "Inspect the telemetry-contracts finding."))},
        "properties": {
            "category": meta.get("category", "uncategorized"),
            "precision": "high",
            "security-severity": "7.0" if meta.get("category") == "privacy-security" else "4.0",
        },
    }


def _result(finding: dict[str, Any]) -> dict[str, Any]:
    code = str(finding.get("code", "telemetry.finding"))
    meta = TAXONOMY.get(code, {})
    level = meta.get("sarif_level") or {"error": "error", "warning": "warning", "info": "note"}.get(str(finding.get("severity")), "warning")
    return {
        "ruleId": code,
        "level": level,
        "message": {"text": str(finding.get("message", code))},
        "locations": [_location(str(finding.get("path") or finding.get("contract_path") or "telemetry-findings"))],
        "properties": {key: value for key, value in finding.items() if key not in {"message"}},
    }


def _location(path_text: str) -> dict[str, Any]:
    uri, line, column = _split_location(path_text)
    physical: dict[str, Any] = {"artifactLocation": {"uri": uri}}
    if line is not None:
        physical["region"] = {"startLine": line, "startColumn": column or 1}
    return {"physicalLocation": physical}


def _split_location(path_text: str) -> tuple[str, int | None, int | None]:
    match = re.match(r"^(.*?):(\d+)(?::(\d+))?(?:-\d+(?::\d+)?)?$", path_text)
    if match and (Path(match.group(1)).suffix or "/" in match.group(1)):
        return match.group(1), int(match.group(2)), int(match.group(3) or 1)
    return path_text, None, None
