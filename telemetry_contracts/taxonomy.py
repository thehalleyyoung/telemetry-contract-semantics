from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .findings import TAXONOMY
from .bug_classes import CODE_TO_BUG_CLASS, soundness_rows

TAXONOMY_SCHEMA_VERSION = "1.1"


def taxonomy_document() -> dict[str, Any]:
    rules = []
    for code in sorted(TAXONOMY):
        entry = TAXONOMY[code]
        rules.append(
            {
                "code": code,
                "category": entry["category"],
                "default_severity": entry["default_severity"],
                "formal_clause": entry["formal_clause"],
                "remediation": entry["remediation"],
                "disclosure_sensitivity": entry["disclosure_sensitivity"],
                "service_owner": entry["service_owner"],
                "sarif_level": entry["sarif_level"],
                "ci": entry["ci"],
                "bug_class": CODE_TO_BUG_CLASS.get(code),
            }
        )
    return {
        "schema": "docs/finding_taxonomy.schema.json",
        "schema_version": TAXONOMY_SCHEMA_VERSION,
        "semantics": {
            "finding": "A finite witness that one telemetry-contract obligation failed or needs operator attention.",
            "formal_clause": "Stable identifier for the well-formedness, satisfaction, adequacy, preservation, static, or input rule that justifies the finding.",
            "ci_mapping": "default_fail_on is the minimum severity a CI gate may use for this rule; sarif_level maps directly to SARIF result.level.",
            "bug_class": "The observability bug class this finding witnesses (see bug_classes); null when the rule is not part of the headline bug-class taxonomy.",
        },
        "summary": {
            "rules": len(rules),
            "categories": dict(sorted(Counter(rule["category"] for rule in rules).items())),
            "default_severities": dict(sorted(Counter(rule["default_severity"] for rule in rules).items())),
            "sarif_levels": dict(sorted(Counter(rule["sarif_level"] for rule in rules).items())),
            "bug_classes": dict(
                sorted(Counter(rule["bug_class"] for rule in rules if rule["bug_class"]).items())
            ),
        },
        "bug_classes": soundness_rows(),
        "rules": rules,
    }


def summarize_findings(paths: list[str | Path]) -> dict[str, Any]:
    sources = []
    findings = []
    for raw_path in paths:
        path = Path(raw_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        extracted = _extract_findings(data)
        sources.append({"path": str(path), "findings": len(extracted)})
        findings.extend(extracted)
    return summarize_finding_records(findings, sources=sources)


def summarize_finding_records(findings: list[dict[str, Any]], *, sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    unknown_codes = sorted({str(item.get("code")) for item in findings if item.get("code") not in TAXONOMY})
    enriched = []
    for item in findings:
        code = str(item.get("code", ""))
        rule = TAXONOMY.get(code, {})
        enriched.append(
            {
                "code": code,
                "severity": item.get("severity"),
                "category": item.get("category", rule.get("category", "uncategorized")),
                "formal_clause": item.get("formal_clause", rule.get("formal_clause")),
                "sarif_level": item.get("sarif_level", rule.get("sarif_level")),
                "service_owner": item.get("service_owner", rule.get("service_owner")),
                "path": item.get("path"),
                "contract_path": item.get("contract_path"),
                "event_index": item.get("event_index"),
            }
        )

    return {
        "sources": sources or [],
        "summary": {
            "findings": len(enriched),
            "unknown_codes": unknown_codes,
            "by_code": dict(sorted(Counter(item["code"] for item in enriched).items())),
            "by_category": dict(sorted(Counter(item["category"] for item in enriched).items())),
            "by_formal_clause": dict(sorted(Counter(str(item["formal_clause"]) for item in enriched).items())),
            "by_sarif_level": dict(sorted(Counter(str(item["sarif_level"]) for item in enriched).items())),
            "by_service_owner": dict(sorted(Counter(str(item["service_owner"]) for item in enriched).items())),
        },
        "findings": enriched,
    }


def taxonomy_report(paths: list[str | Path] | None = None) -> dict[str, Any]:
    report = taxonomy_document()
    if paths:
        report["observed_findings"] = summarize_findings(paths)
    return report


def format_taxonomy_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Finding taxonomy",
        "",
        f"- Schema version: `{report['schema_version']}`",
        f"- Rules: {summary['rules']}",
        f"- Categories: `{json.dumps(summary['categories'], sort_keys=True)}`",
        f"- Default severities: `{json.dumps(summary['default_severities'], sort_keys=True)}`",
        f"- SARIF levels: `{json.dumps(summary['sarif_levels'], sort_keys=True)}`",
        "",
        "## Rule catalog",
        "",
        "| Code | Category | Severity | Formal clause | SARIF | CI fail-on | Disclosure | Owner | Remediation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rule in report["rules"]:
        lines.append(
            "| {code} | {category} | {severity} | {clause} | {sarif} | {fail_on} | {disclosure} | {owner} | {remediation} |".format(
                code=_md(rule["code"]),
                category=_md(rule["category"]),
                severity=_md(rule["default_severity"]),
                clause=_md(rule["formal_clause"]),
                sarif=_md(rule["sarif_level"]),
                fail_on=_md(rule["ci"]["default_fail_on"]),
                disclosure=_md(rule["disclosure_sensitivity"]),
                owner=_md(rule["service_owner"]),
                remediation=_md(rule["remediation"]),
            )
        )

    observed = report.get("observed_findings")
    if observed:
        obs_summary = observed["summary"]
        lines.extend(
            [
                "",
                "## Observed finding coverage",
                "",
                f"- Findings: {obs_summary['findings']}",
                f"- Unknown codes: `{json.dumps(obs_summary['unknown_codes'])}`",
                f"- By code: `{json.dumps(obs_summary['by_code'], sort_keys=True)}`",
                f"- By category: `{json.dumps(obs_summary['by_category'], sort_keys=True)}`",
                f"- By formal clause: `{json.dumps(obs_summary['by_formal_clause'], sort_keys=True)}`",
                f"- By SARIF level: `{json.dumps(obs_summary['by_sarif_level'], sort_keys=True)}`",
                f"- By service owner: `{json.dumps(obs_summary['by_service_owner'], sort_keys=True)}`",
                "",
                "| Source | Findings |",
                "| --- | ---: |",
            ]
        )
        for source in observed["sources"]:
            lines.append(f"| {_md(source['path'])} | {source['findings']} |")
        lines.extend(["", "| Code | Category | Formal clause | Severity | SARIF | Path |", "| --- | --- | --- | --- | --- | --- |"])
        for finding in observed["findings"]:
            lines.append(
                f"| {_md(finding['code'])} | {_md(str(finding['category']))} | {_md(str(finding['formal_clause']))} | "
                f"{_md(str(finding['severity']))} | {_md(str(finding['sarif_level']))} | {_md(str(finding['path']))} |"
            )
    lines.append("")
    return "\n".join(lines)


def _extract_findings(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        direct = data.get("findings")
        if isinstance(direct, list):
            return [item for item in direct if isinstance(item, dict)]
        cases = data.get("cases")
        if isinstance(cases, list):
            findings = []
            for case in cases:
                if isinstance(case, dict) and isinstance(case.get("findings"), list):
                    findings.extend(item for item in case["findings"] if isinstance(item, dict))
            return findings
    raise ValueError("expected a JSON object with a findings array or benchmark cases containing findings")


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
