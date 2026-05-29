from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .findings import Finding, has_at_least
from .loader import ContractLoadError, load_contract, load_jsonl
from .scenario import check_scenario, choose_scenario
from .static_checker import check_sources
from .validator import validate_events


class BenchmarkLoadError(ValueError):
    """Raised when a benchmark config cannot be loaded."""


def run_benchmark(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    config = _load_json_object(path, "benchmark config")
    cases = config.get("cases")
    if not isinstance(cases, list) or not cases:
        raise BenchmarkLoadError(f"benchmark config must contain a non-empty 'cases' list: {path}")

    started = time.perf_counter()
    case_results = [_run_case(case, path.parent) for case in cases]
    runtime_ms = round((time.perf_counter() - started) * 1000, 3)
    findings = [finding for case in case_results for finding in case["findings"]]
    unique_contracts = {contract for case in case_results for contract in case["contract_paths"]}
    summary = {
        "name": config.get("name", path.stem),
        "config": str(path),
        "contracts": len(unique_contracts),
        "events": sum(case["events"] for case in case_results),
        "findings": len(findings),
        "findings_by_code": dict(sorted(Counter(finding["code"] for finding in findings).items())),
        "findings_by_severity": dict(sorted(Counter(finding["severity"] for finding in findings).items())),
        "runtime_ms": runtime_ms,
        "pass": all(case["pass"] for case in case_results),
    }
    return {"summary": summary, "cases": case_results}


def _run_case(case: Any, base_dir: Path) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise BenchmarkLoadError("benchmark case entries must be objects")
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise BenchmarkLoadError("benchmark case must declare a non-empty string id")

    metadata = _load_metadata(case, base_dir)
    contract_paths = _case_contract_paths(case, base_dir)
    events_path = _resolve_optional_path(case, "events", base_dir)
    source_paths = _case_source_paths(case, base_dir)
    if events_path is None and not source_paths:
        raise BenchmarkLoadError(f"case {case_id}: must provide events and/or sources")
    events = load_jsonl(events_path) if events_path is not None else []

    started = time.perf_counter()
    all_findings: list[Finding] = []
    scenario_ids = case.get("scenarios", [])
    if scenario_ids is None:
        scenario_ids = []
    if not isinstance(scenario_ids, list):
        raise BenchmarkLoadError(f"case {case_id}: scenarios must be a list")

    for contract_path in contract_paths:
        contract = load_contract(contract_path)
        if events_path is not None:
            all_findings.extend(validate_events(contract, events, strict=True if case.get("strict") is True else None))
        for scenario_id in scenario_ids:
            if not isinstance(scenario_id, str):
                raise BenchmarkLoadError(f"case {case_id}: scenario ids must be strings")
            if events_path is None:
                raise BenchmarkLoadError(f"case {case_id}: scenario checks require events")
            all_findings.extend(check_scenario(contract, events, choose_scenario(contract, scenario_id=scenario_id)))
        if source_paths:
            all_findings.extend(check_sources(contract, source_paths))

    runtime_ms = round((time.perf_counter() - started) * 1000, 3)
    finding_dicts = [finding.to_dict() for finding in all_findings]
    expected = case.get("expected_findings", metadata.get("expected_findings", []))
    label_metrics = _label_metrics(finding_dicts, expected, case_id)
    validation_pass = not has_at_least(all_findings, "error")
    case_pass = label_metrics["pass"] if label_metrics is not None else validation_pass
    return {
        "id": case_id,
        "description": case.get("description", metadata.get("title", "")),
        "contract_paths": [str(path) for path in contract_paths],
        "events_path": str(events_path) if events_path is not None else None,
        "source_paths": [str(path) for path in source_paths],
        "checks": {
            "runtime": events_path is not None,
            "scenario": bool(scenario_ids),
            "static": bool(source_paths),
            "strict": case.get("strict") is True,
        },
        "events": len(events),
        "findings": finding_dicts,
        "metrics": {
            "contracts": len(contract_paths),
            "events": len(events),
            "findings": len(finding_dicts),
            "findings_by_code": dict(sorted(Counter(item["code"] for item in finding_dicts).items())),
            "findings_by_severity": dict(sorted(Counter(item["severity"] for item in finding_dicts).items())),
            "runtime_ms": runtime_ms,
            "validation_pass": validation_pass,
            "pass": case_pass,
            "labels": label_metrics,
        },
        "pass": case_pass,
    }


def _case_contract_paths(case: dict[str, Any], base_dir: Path) -> list[Path]:
    if "contracts" in case:
        contracts = case["contracts"]
        if not isinstance(contracts, list) or not contracts:
            raise BenchmarkLoadError(f"case {case.get('id')}: contracts must be a non-empty list")
        return [_resolve_path(str(item), base_dir) for item in contracts]
    return [_resolve_required_path(case, "contract", base_dir)]


def _case_source_paths(case: dict[str, Any], base_dir: Path) -> list[Path]:
    sources = case.get("sources", [])
    if sources in (None, []):
        return []
    if isinstance(sources, str):
        sources = [sources]
    if not isinstance(sources, list):
        raise BenchmarkLoadError(f"case {case.get('id')}: sources must be a path string or list")
    return [_resolve_path(str(item), base_dir) for item in sources]


def _load_metadata(case: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    metadata_path = case.get("metadata")
    if metadata_path is None:
        return {}
    if not isinstance(metadata_path, str):
        raise BenchmarkLoadError(f"case {case.get('id')}: metadata must be a path string")
    return _load_json_object(_resolve_path(metadata_path, base_dir), "case metadata")


def _resolve_required_path(case: dict[str, Any], key: str, base_dir: Path) -> Path:
    value = case.get(key)
    if not isinstance(value, str) or not value:
        raise BenchmarkLoadError(f"case {case.get('id')}: missing required path '{key}'")
    return _resolve_path(value, base_dir)


def _resolve_optional_path(case: dict[str, Any], key: str, base_dir: Path) -> Path | None:
    value = case.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise BenchmarkLoadError(f"case {case.get('id')}: invalid optional path '{key}'")
    return _resolve_path(value, base_dir)


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    path = Path(os.path.normpath(path))
    if not path.exists():
        raise ContractLoadError(f"benchmark path does not exist: {path}")
    return path


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise ContractLoadError(f"{label} does not exist: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkLoadError(f"invalid JSON in {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BenchmarkLoadError(f"{label} root must be an object: {path}")
    return data


def _label_metrics(findings: list[dict[str, Any]], expected: Any, case_id: str) -> dict[str, Any] | None:
    if expected in (None, []):
        return None
    if not isinstance(expected, list):
        raise BenchmarkLoadError(f"case {case_id}: expected_findings must be a list")
    for item in expected:
        if not isinstance(item, dict) or not isinstance(item.get("code"), str):
            raise BenchmarkLoadError(f"case {case_id}: each expected finding label must be an object with a code")

    matched_indices: set[int] = set()
    missing: list[dict[str, Any]] = []
    for label in expected:
        match_index = next((index for index, finding in enumerate(findings) if index not in matched_indices and _matches_label(finding, label)), None)
        if match_index is None:
            missing.append(label)
        else:
            matched_indices.add(match_index)
    unexpected = [finding for index, finding in enumerate(findings) if index not in matched_indices]
    matched = len(matched_indices)
    precision = matched / (matched + len(unexpected)) if matched or unexpected else 1.0
    recall = matched / len(expected) if expected else 1.0
    return {
        "expected": len(expected),
        "matched": matched,
        "missing": missing,
        "unexpected": unexpected,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "pass": not missing and not unexpected,
    }


def _matches_label(finding: dict[str, Any], label: dict[str, Any]) -> bool:
    for key in ("code", "severity", "path", "contract_path", "event_index"):
        if key in label and finding.get(key) != label[key]:
            return False
    if "path_suffix" in label and not str(finding.get("path", "")).endswith(str(label["path_suffix"])):
        return False
    return True


def format_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Benchmark: {summary['name']}",
        "",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Contracts: {summary['contracts']}",
        f"- Events: {summary['events']}",
        f"- Findings: {summary['findings']}",
        f"- Runtime: {summary['runtime_ms']} ms",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        f"- Findings by severity: `{json.dumps(summary['findings_by_severity'], sort_keys=True)}`",
        "",
        "| Case | Checks | Pass | Events | Findings | Validation pass | Label precision | Label recall | Runtime ms |",
        "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for case in report["cases"]:
        metrics = case["metrics"]
        labels = metrics.get("labels") or {}
        precision = labels.get("precision", "n/a")
        recall = labels.get("recall", "n/a")
        checks = ",".join(name for name, enabled in case.get("checks", {}).items() if enabled) or "none"
        lines.append(
            f"| {case['id']} | {checks} | `{str(case['pass']).lower()}` | {metrics['events']} | {metrics['findings']} | "
            f"`{str(metrics['validation_pass']).lower()}` | {precision} | {recall} | {metrics['runtime_ms']} |"
        )
    lines.append("")
    return "\n".join(lines)
