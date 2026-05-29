from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .findings import TAXONOMY
from .taxonomy import _extract_findings

EXPLAIN_SCHEMA_VERSION = "1.0"

_CLAUSE_MEANINGS = {
    "WF": "well-formedness rule checked before telemetry is evaluated",
    "SAT": "runtime satisfaction rule in the finite-trace relation T ⊨ C",
    "STRICT": "closed-world strict-mode side condition on T ⊨ C",
    "ADEQ": "diagnosability adequacy rule for an incident question",
    "PRES": "semantic-preservation rule comparing source and transformed traces",
    "HYP": "hyperproperty rule quantified over pairs or sets of finite telemetry traces",
    "STATIC": "static source-code evidence rule approximating telemetry emission",
    "SCENARIO": "scenario selection or scenario well-formedness rule",
    "INPUT": "input loading and parsing rule",
}

_IMPACT_BY_CATEGORY = {
    "contract": "Contract authors get an invalid or ambiguous specification, so downstream validation cannot make a reliable semantic claim.",
    "schema": "Emitted telemetry no longer matches the modeled data domain, which can break dashboards, alerts, joins, or strict drift gates.",
    "diagnosability": "An incident question may be unanswered because the finite trace lacks required evidence, fields, correlation, severity, or ordering.",
    "privacy-security": "Telemetry may disclose sensitive data or fail to document an approved privacy-preserving transformation; handle reports under responsible-disclosure rules.",
    "operability": "Telemetry may become expensive, noisy, or hard to index because labels, cardinality, or policies are not bounded.",
    "static-coverage": "The checked source may not emit the required telemetry evidence on the reviewed code path.",
    "scenario": "The selected incident question cannot be evaluated until the scenario is made well formed or selected explicitly.",
    "preservation": "A collector/exporter or policy transformation can remove evidence that previously satisfied the contract or incident question.",
    "input": "The requested artifact could not be parsed, so no contract-satisfaction claim was produced.",
}

_EXAMPLE_TRACE_BY_PREFIX = {
    "WF": ["contract JSON", "well-formedness check", "reject malformed obligation before runtime"],
    "SAT": ["contract C", "finite telemetry trace T", "evaluate T ⊨ C and emit a witness/counterexample finding"],
    "STRICT": ["contract C with strict mode", "finite telemetry trace T", "check closed-world service, signal, field, and transformation side conditions"],
    "ADEQ": ["incident scenario question", "finite telemetry trace T", "check whether each minimum observation has a witness"],
    "PRES": ["source trace T", "transformed trace T′", "check that satisfied obligations in T remain satisfied in T′"],
    "HYP": ["finite trace set {T₁…Tₙ}", "pairwise or set monitor", "emit a privacy-risk witness when a relation between traces violates the hyperproperty"],
    "STATIC": ["source file", "instrumentation/logging literals", "map source evidence to contract obligation or privacy risk"],
    "SCENARIO": ["contract scenarios", "selected id/question", "choose the unique incident question to evaluate"],
    "INPUT": ["path or JSON artifact", "loader", "produce parse error instead of an unsound validation claim"],
}


def explain_finding(code: str, example_paths: list[str | Path] | None = None) -> dict[str, Any]:
    if code not in TAXONOMY:
        return {
            "schema_version": EXPLAIN_SCHEMA_VERSION,
            "known": False,
            "code": code,
            "message": f"Unknown finding code: {code}",
            "known_codes": sorted(TAXONOMY),
        }

    rule = TAXONOMY[code]
    clause = str(rule["formal_clause"])
    prefix = clause.split(".", 1)[0]
    category = str(rule["category"])
    observed = _observed_examples(code, example_paths or [])
    return {
        "schema_version": EXPLAIN_SCHEMA_VERSION,
        "known": True,
        "code": code,
        "category": category,
        "default_severity": rule["default_severity"],
        "formal_clause": clause,
        "formal_meaning": _formal_meaning(prefix, clause, category),
        "practical_impact": _IMPACT_BY_CATEGORY.get(category, "This finding identifies a telemetry-contract obligation requiring owner review."),
        "example_trace_shape": _EXAMPLE_TRACE_BY_PREFIX.get(prefix, ["artifact", "checker", "finding"]),
        "concrete_fix": rule["remediation"],
        "service_owner": rule["service_owner"],
        "disclosure_sensitivity": rule["disclosure_sensitivity"],
        "sarif_level": rule["sarif_level"],
        "ci": rule["ci"],
        "observed_examples": observed,
        "bounded_claim": _bounded_claim(code, observed),
    }


def format_explanation_markdown(report: dict[str, Any]) -> str:
    if not report.get("known"):
        lines = [
            f"# Unknown finding code `{_md(str(report['code']))}`",
            "",
            _md(str(report["message"])),
            "",
            "Known codes include:",
        ]
        lines.extend(f"- `{_md(code)}`" for code in report["known_codes"][:20])
        if len(report["known_codes"]) > 20:
            lines.append(f"- … {len(report['known_codes']) - 20} more")
        lines.append("")
        return "\n".join(lines)

    lines = [
        f"# Finding explanation: `{_md(str(report['code']))}`",
        "",
        f"- Category: `{_md(str(report['category']))}`",
        f"- Default severity: `{_md(str(report['default_severity']))}`",
        f"- Formal clause: `{_md(str(report['formal_clause']))}`",
        f"- SARIF level: `{_md(str(report['sarif_level']))}`",
        f"- Service owner route: {_md(str(report['service_owner']))}",
        f"- Disclosure sensitivity: `{_md(str(report['disclosure_sensitivity']))}`",
        "",
        "## Formal meaning",
        "",
        _md(str(report["formal_meaning"])),
        "",
        "## Practical impact",
        "",
        _md(str(report["practical_impact"])),
        "",
        "## Example trace shape",
        "",
    ]
    lines.extend(f"{index}. {_md(str(item))}" for index, item in enumerate(report["example_trace_shape"], 1))
    lines.extend([
        "",
        "## Concrete fix",
        "",
        _md(str(report["concrete_fix"])),
        "",
        "## CI / baseline key",
        "",
        f"- Default fail-on: `{_md(str(report['ci']['default_fail_on']))}`",
        f"- Baseline key fields: `{_md(json.dumps(report['ci']['baseline_key_fields']))}`",
        "",
        "## Observed examples",
        "",
    ])
    examples = report.get("observed_examples", [])
    if examples:
        lines.extend(["| Source | Severity | Path | Event index | Message |", "| --- | --- | --- | ---: | --- |"] )
        for item in examples:
            lines.append(
                f"| {_md(str(item['source']))} | {_md(str(item.get('severity', '')))} | {_md(str(item.get('path', '')))} | "
                f"{_md(str(item.get('event_index', '')))} | {_md(str(item.get('message', '')))} |"
            )
    else:
        lines.append("No matching examples were supplied. Pass `--examples REPORT.json` to attach concrete public or benchmark findings.")
    lines.extend(["", "## Bounded evidence claim", "", _md(str(report["bounded_claim"])), ""] )
    return "\n".join(lines)


def _formal_meaning(prefix: str, clause: str, category: str) -> str:
    base = _CLAUSE_MEANINGS.get(prefix, "semantic rule in the telemetry-contract checker")
    return f"`{clause}` is a {base}. The deterministic checker emits this finding when the corresponding {category} obligation has a finite counterexample or missing witness."


def _bounded_claim(code: str, observed: list[dict[str, Any]]) -> str:
    if not observed:
        return f"This explanation defines how `{code}` is interpreted by the current taxonomy; no concrete artifact was attached to this report."
    sources = sorted({str(item["source"]) for item in observed})
    return f"For the supplied artifacts, `{code}` appears {len(observed)} time(s) across {len(sources)} source report(s): {', '.join(sources)}. This does not claim completeness beyond those checked-in finite reports."


def _observed_examples(code: str, paths: list[str | Path]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for raw_path in paths:
        path = Path(raw_path)
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in _extract_findings(data):
            if item.get("code") == code:
                examples.append(
                    {
                        "source": str(path),
                        "severity": item.get("severity"),
                        "message": item.get("message"),
                        "path": item.get("path"),
                        "contract_path": item.get("contract_path"),
                        "event_index": item.get("event_index"),
                    }
                )
    return examples


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
