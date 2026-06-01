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


# ---------------------------------------------------------------------------
# Pipeline differential SARIF (separate rule namespace from the finding taxonomy)
# ---------------------------------------------------------------------------

_DIFF_RULES: dict[str, dict[str, str]] = {
    "pipeline.diff.regression": {"text": "A pipeline round regressed safety or diagnosability."},
    "pipeline.diff.score-drop": {"text": "The diagnosability score dropped after applying changes."},
    "pipeline.diff.new-finding": {"text": "A new analysis finding was introduced."},
    "pipeline.diff.newly-unanswerable": {"text": "An incident question became unanswerable."},
    "pipeline.diff.improvement": {"text": "Diagnosability improved after applying changes."},
}


def _diff_rule(rule_id: str) -> dict[str, Any]:
    meta = _DIFF_RULES[rule_id]
    return {
        "id": rule_id,
        "name": rule_id,
        "shortDescription": {"text": meta["text"]},
        "fullDescription": {"text": meta["text"]},
        "help": {"text": meta["text"]},
        "properties": {"category": "pipeline-differential", "precision": "high"},
    }


def pipeline_differential_to_sarif(report: dict[str, Any], *, tool_name: str = "telemetry-contracts") -> dict[str, Any]:
    """Emit a CI-ready SARIF run for a pipeline's improvement/regression story.

    Uses a dedicated ``pipeline.diff.*`` rule namespace so it never collides with
    the finding taxonomy. Introduced taxonomy findings carry their original code
    in ``properties.finding_code``.
    """

    final = report.get("final") or {}
    overall = final.get("overall_differential") or {}
    results: list[dict[str, Any]] = []
    used_rules: set[str] = set()

    def add(rule_id: str, level: str, text: str, props: dict[str, Any]) -> None:
        used_rules.add(rule_id)
        results.append({
            "ruleId": rule_id,
            "level": level,
            "message": {"text": text},
            "locations": [_location("pipeline-differential")],
            "properties": props,
        })

    score_delta = overall.get("score_delta", 0)
    if score_delta < 0:
        add("pipeline.diff.score-drop", "error", f"Diagnosability score dropped by {-score_delta}.",
            {"score_delta": score_delta})
    for code, count in sorted((overall.get("introduced_findings") or {}).items()):
        add("pipeline.diff.new-finding", "error", f"Introduced finding {code} (+{count}).",
            {"finding_code": code, "after_increase": count})
    for question in overall.get("newly_unanswerable") or []:
        add("pipeline.diff.newly-unanswerable", "error", f"Incident question '{question}' became unanswerable.",
            {"question": question})
    if report.get("regressed"):
        add("pipeline.diff.regression", "error", "One or more rounds were quarantined for regressing safety.",
            {"stopped_reason": report.get("stopped_reason")})
    if score_delta > 0 and not overall.get("regressions"):
        add("pipeline.diff.improvement", "note",
            f"Diagnosability improved by {score_delta}; "
            f"{len(overall.get('newly_answerable') or [])} question(s) newly answerable.",
            {"score_delta": score_delta, "newly_answerable": overall.get("newly_answerable") or []})

    rules = [_diff_rule(rule_id) for rule_id in sorted(used_rules)]
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {"driver": {"name": tool_name, "informationUri": "https://github.com/thehalleyyoung/telemetry-contract-semantics", "rules": rules}},
                "results": results,
            }
        ],
    }
