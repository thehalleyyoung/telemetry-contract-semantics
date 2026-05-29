from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .findings import Finding, TAXONOMY, has_at_least
from .loader import ContractLoadError, load_contract, load_jsonl
from .scenario import check_scenario, choose_scenario
from .static_checker import check_sources
from .validator import validate_events


class BenchmarkLoadError(ValueError):
    """Raised when a benchmark config cannot be loaded."""


FILTER_KEYS = {
    "case_id": "id",
    "tag": "tags",
    "check_type": "check_types",
    "dataset": "dataset",
    "expected_failure_mode": "expected_failure_modes",
    "semantics_feature": "semantics_features",
    "service_owner": "service_owner",
    "disclosure_status": "disclosure_status",
}


def run_benchmark(config_path: str | Path, filters: dict[str, list[str] | None] | None = None) -> dict[str, Any]:
    path = Path(config_path)
    config = _load_json_object(path, "benchmark config")
    cases = config.get("cases")
    if not isinstance(cases, list) or not cases:
        raise BenchmarkLoadError(f"benchmark config must contain a non-empty 'cases' list: {path}")

    active_cases = _filter_cases(cases, filters or {})
    if not active_cases:
        raise BenchmarkLoadError(f"benchmark filters selected no cases: {filters}")

    started = time.perf_counter()
    case_results = [_run_case(case, path.parent) for case in active_cases]
    runtime_ms = round((time.perf_counter() - started) * 1000, 3)
    findings = [finding for case in case_results for finding in case["findings"]]
    unique_contracts = {contract for case in case_results for contract in case["contract_paths"]}
    label_totals = _aggregate_label_metrics(case_results)
    total_events = sum(case["events"] for case in case_results)
    summary = {
        "name": config.get("name", path.stem),
        "config": str(path),
        "filters": _compact_filters(filters or {}),
        "cases": len(case_results),
        "contracts": len(unique_contracts),
        "events": total_events,
        "findings": len(findings),
        "findings_by_code": dict(sorted(Counter(finding["code"] for finding in findings).items())),
        "findings_by_severity": dict(sorted(Counter(finding["severity"] for finding in findings).items())),
        "runtime_ms": runtime_ms,
        "runtime_per_k_events_ms": _per_k(runtime_ms, total_events),
        "findings_per_k_events": _per_k(len(findings), total_events),
        "label_metrics": label_totals,
        "memory_envelope": _aggregate_memory_envelope(case_results),
        "import_loss_rate": _aggregate_import_loss_rate(case_results),
        "top_remediations": _top_remediations(findings),
        "datasets": sorted({str(case.get("dataset_metadata", {}).get("id") or case.get("dataset", "")) for case in case_results if case.get("dataset_metadata") or case.get("dataset")}),
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
    diagnostics_path = _resolve_optional_path(case, "import_diagnostics", base_dir)
    if events_path is None and not source_paths and diagnostics_path is None:
        raise BenchmarkLoadError(f"case {case_id}: must provide events, sources, and/or import_diagnostics")
    events = load_jsonl(events_path) if events_path is not None else []
    import_report = _load_import_diagnostics(diagnostics_path) if diagnostics_path is not None else None

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
    diagnostic_findings = _diagnostic_findings(import_report)

    runtime_ms = round((time.perf_counter() - started) * 1000, 3)
    finding_dicts = [finding.to_dict() for finding in all_findings] + diagnostic_findings
    expected = case.get("expected_findings", metadata.get("expected_findings", []))
    label_metrics = _label_metrics(finding_dicts, expected, case_id)
    validation_pass = not has_at_least(all_findings, "error") and not any(item["severity"] == "error" for item in diagnostic_findings)
    case_pass = label_metrics["pass"] if label_metrics is not None else validation_pass
    dataset_metadata = _dataset_metadata(case, metadata)
    tags = _strings(case.get("tags", metadata.get("tags", [])))
    check_types = _case_check_types(events_path, source_paths, scenario_ids, case, diagnostics_path)
    return {
        "id": case_id,
        "description": case.get("description", metadata.get("title", "")),
        "tags": tags,
        "dataset": case.get("dataset", metadata.get("id", dataset_metadata.get("id"))),
        "dataset_metadata": dataset_metadata,
        "expected_failure_modes": _strings(case.get("expected_failure_modes", metadata.get("expected_failure_modes", []))),
        "semantics_features": _strings(case.get("semantics_features", metadata.get("semantics_features", []))),
        "service_owner": case.get("service_owner", metadata.get("service_owner", dataset_metadata.get("owner", "contract service owner"))),
        "disclosure_status": case.get("disclosure_status", metadata.get("disclosure_status", dataset_metadata.get("disclosure_status", "unspecified"))),
        "contract_paths": [str(path) for path in contract_paths],
        "events_path": str(events_path) if events_path is not None else None,
        "source_paths": [str(path) for path in source_paths],
        "import_diagnostics_path": str(diagnostics_path) if diagnostics_path is not None else None,
        "checks": {name: name in check_types for name in ("runtime", "scenario", "static", "strict", "import_diagnostics")},
        "events": len(events),
        "findings": finding_dicts,
        "import_diagnostics": import_report,
        "metrics": {
            "contracts": len(contract_paths),
            "events": len(events),
            "findings": len(finding_dicts),
            "findings_by_code": dict(sorted(Counter(item["code"] for item in finding_dicts).items())),
            "findings_by_severity": dict(sorted(Counter(item["severity"] for item in finding_dicts).items())),
            "runtime_ms": runtime_ms,
            "runtime_per_k_events_ms": _per_k(runtime_ms, len(events)),
            "findings_per_k_events": _per_k(len(finding_dicts), len(events)),
            "memory_envelope": _case_memory_envelope(events, source_paths, import_report),
            "import_loss_rate": _case_import_loss_rate(import_report),
            "diagnosability_score_change": _diagnosability_score_change(finding_dicts),
            "validation_pass": validation_pass,
            "pass": case_pass,
            "labels": label_metrics,
        },
        "pass": case_pass,
    }


def compare_benchmark_reports(baseline_path: str | Path, candidate_path: str | Path) -> dict[str, Any]:
    baseline = _load_json_object(Path(baseline_path), "baseline benchmark report")
    candidate = _load_json_object(Path(candidate_path), "candidate benchmark report")
    base_cases = {case.get("id"): case for case in baseline.get("cases", []) if isinstance(case, dict)}
    cand_cases = {case.get("id"): case for case in candidate.get("cases", []) if isinstance(case, dict)}
    changed_cases: list[dict[str, Any]] = []
    for case_id in sorted(set(base_cases) | set(cand_cases)):
        before = base_cases.get(case_id)
        after = cand_cases.get(case_id)
        if before is None or after is None:
            changed_cases.append({"id": case_id, "change": "added" if after else "removed"})
            continue
        metrics_before = before.get("metrics", {})
        metrics_after = after.get("metrics", {})
        delta = {
            "findings": metrics_after.get("findings", 0) - metrics_before.get("findings", 0),
            "runtime_ms": round(metrics_after.get("runtime_ms", 0) - metrics_before.get("runtime_ms", 0), 3),
            "label_precision": _delta_metric(metrics_before, metrics_after, "precision"),
            "label_recall": _delta_metric(metrics_before, metrics_after, "recall"),
            "semantic_coverage": sorted(set(after.get("semantics_features", [])) - set(before.get("semantics_features", []))),
        }
        before_codes = Counter(metrics_before.get("findings_by_code", {}))
        after_codes = Counter(metrics_after.get("findings_by_code", {}))
        code_delta = {code: after_codes[code] - before_codes[code] for code in sorted(set(before_codes) | set(after_codes)) if after_codes[code] != before_codes[code]}
        if any(delta.values()) or code_delta or before.get("pass") != after.get("pass"):
            changed_cases.append({"id": case_id, "change": "changed", "pass_before": before.get("pass"), "pass_after": after.get("pass"), "delta": delta, "findings_by_code_delta": code_delta})
    base_top = baseline.get("summary", {}).get("top_remediations", [])
    cand_top = candidate.get("summary", {}).get("top_remediations", [])
    return {
        "summary": {
            "baseline": str(baseline_path),
            "candidate": str(candidate_path),
            "changed_cases": len(changed_cases),
            "findings_delta": candidate.get("summary", {}).get("findings", 0) - baseline.get("summary", {}).get("findings", 0),
            "runtime_ms_delta": round(candidate.get("summary", {}).get("runtime_ms", 0) - baseline.get("summary", {}).get("runtime_ms", 0), 3),
            "top_remediation_groups_changed": base_top != cand_top,
            "pass": not changed_cases,
        },
        "cases": changed_cases,
        "top_remediations_before": base_top,
        "top_remediations_after": cand_top,
    }


def format_diff_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Benchmark diff",
        "",
        f"- Baseline: `{summary['baseline']}`",
        f"- Candidate: `{summary['candidate']}`",
        f"- Changed cases: {summary['changed_cases']}",
        f"- Findings delta: {summary['findings_delta']}",
        f"- Runtime delta: {summary['runtime_ms_delta']} ms",
        f"- Top remediation groups changed: `{str(summary['top_remediation_groups_changed']).lower()}`",
        "",
        "| Case | Change | Pass before | Pass after | Findings Δ | Runtime Δ ms | Code deltas | Semantic coverage added |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for case in report["cases"]:
        delta = case.get("delta", {})
        lines.append(
            f"| {case['id']} | {case['change']} | `{str(case.get('pass_before')).lower()}` | `{str(case.get('pass_after')).lower()}` | "
            f"{delta.get('findings', 'n/a')} | {delta.get('runtime_ms', 'n/a')} | `{json.dumps(case.get('findings_by_code_delta', {}), sort_keys=True)}` | "
            f"{', '.join(delta.get('semantic_coverage', [])) or 'none'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _case_contract_paths(case: dict[str, Any], base_dir: Path) -> list[Path]:
    if "contracts" in case:
        contracts = case["contracts"]
        if not isinstance(contracts, list) or not contracts:
            raise BenchmarkLoadError(f"case {case.get('id')}: contracts must be a non-empty list")
        return [_resolve_path(str(item), base_dir) for item in contracts]
    if "contract" not in case:
        return []
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


def _load_import_diagnostics(path: Path) -> dict[str, Any]:
    data = _load_json_object(path, "import diagnostics")
    if not isinstance(data.get("summary"), dict) or not isinstance(data.get("diagnostics", []), list):
        raise BenchmarkLoadError(f"import diagnostics must contain summary and diagnostics: {path}")
    return data


def _diagnostic_findings(report: dict[str, Any] | None) -> list[dict[str, Any]]:
    if report is None:
        return []
    findings: list[dict[str, Any]] = []
    for index, item in enumerate(report.get("diagnostics", [])):
        if not isinstance(item, dict):
            continue
        severity = item.get("severity") if item.get("severity") in {"info", "warning", "error"} else "warning"
        code = str(item.get("code", "otlp.import_diagnostic"))
        finding = Finding(severity, code, str(item.get("message", code)), str(item.get("path", f"diagnostics[{index}]")), details={"invalidates_contract_claim": bool(item.get("invalidates_contract_claim")), **(item.get("details") if isinstance(item.get("details"), dict) else {})}).to_dict()
        findings.append(finding)
    return findings


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
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "expected": len(expected),
        "matched": matched,
        "missing": missing,
        "unexpected": unexpected,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "pass": not missing and not unexpected,
    }


def _matches_label(finding: dict[str, Any], label: dict[str, Any]) -> bool:
    for key in ("code", "severity", "path", "contract_path", "event_index"):
        if key in label and finding.get(key) != label[key]:
            return False
    if "path_suffix" in label and not str(finding.get("path", "")).endswith(str(label["path_suffix"])):
        return False
    return True


def _filter_cases(cases: list[Any], filters: dict[str, list[str] | None]) -> list[Any]:
    compact = _compact_filters(filters)
    if not compact:
        return cases
    selected: list[Any] = []
    for case in cases:
        if not isinstance(case, dict):
            selected.append(case)
            continue
        if all(_case_matches_filter(case, key, values) for key, values in compact.items()):
            selected.append(case)
    return selected


def _case_matches_filter(case: dict[str, Any], key: str, values: list[str]) -> bool:
    config_key = FILTER_KEYS[key]
    raw = case.get(config_key)
    if config_key == "check_types":
        raw = case.get("check_types") or _declared_check_types(case)
    if isinstance(raw, list):
        present = {str(item) for item in raw}
    elif raw is None:
        present = set()
    else:
        present = {str(raw)}
    return bool(present.intersection(values))


def _declared_check_types(case: dict[str, Any]) -> list[str]:
    checks: list[str] = []
    if case.get("events"):
        checks.append("runtime")
    if case.get("sources"):
        checks.append("static")
    if case.get("scenarios"):
        checks.append("scenario")
    if case.get("strict") is True:
        checks.append("strict")
    if case.get("import_diagnostics"):
        checks.append("import_diagnostics")
    return checks


def _compact_filters(filters: dict[str, list[str] | None]) -> dict[str, list[str]]:
    return {key: [str(item) for item in values if str(item)] for key, values in filters.items() if key in FILTER_KEYS and values}


def _strings(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _case_check_types(events_path: Path | None, source_paths: list[Path], scenario_ids: list[Any], case: dict[str, Any], diagnostics_path: Path | None) -> set[str]:
    checks: set[str] = set()
    if events_path is not None:
        checks.add("runtime")
    if source_paths:
        checks.add("static")
    if scenario_ids:
        checks.add("scenario")
    if case.get("strict") is True:
        checks.add("strict")
    if diagnostics_path is not None:
        checks.add("import_diagnostics")
    return checks


def _dataset_metadata(case: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    dataset = metadata.get("dataset_metadata") if isinstance(metadata.get("dataset_metadata"), dict) else {}
    result = {
        "id": case.get("dataset", metadata.get("id", dataset.get("id", case.get("id")))),
        "source_url": metadata.get("source_url") or metadata.get("source_repository") or dataset.get("source_url"),
        "retrieval_date": metadata.get("retrieval_date") or dataset.get("retrieval_date"),
        "version": metadata.get("commit") or metadata.get("document_version") or dataset.get("version"),
        "license": metadata.get("license") or dataset.get("license"),
        "checksum": metadata.get("file_sha") or metadata.get("checksum") or metadata.get("checksums") or dataset.get("checksum"),
        "reconstruction_status": metadata.get("fixture_status") or metadata.get("runtime_fixture") or dataset.get("reconstruction_status"),
        "disclosure_status": metadata.get("disclosure_status", dataset.get("disclosure_status", case.get("disclosure_status", "public-fixture"))),
        "transformations": metadata.get("transformations", dataset.get("transformations", [])),
        "labels": metadata.get("labels_description") or ("expected_findings" if metadata.get("expected_findings") else None),
        "validity_threats": metadata.get("validity_threats", dataset.get("validity_threats", [])),
    }
    return {key: value for key, value in result.items() if value not in (None, [], {})}


def _per_k(value: float, events: int) -> float:
    return round((value / events) * 1000, 6) if events else 0.0


def _case_memory_envelope(events: list[dict[str, Any]], source_paths: list[Path], import_report: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "events_indexed": len(events),
        "source_files": len(source_paths),
        "import_records": (import_report or {}).get("summary", {}).get("records", 0),
        "diagnostics": (import_report or {}).get("summary", {}).get("diagnostics", 0),
    }


def _aggregate_memory_envelope(cases: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ("events_indexed", "source_files", "import_records", "diagnostics")
    return {key: sum(case.get("metrics", {}).get("memory_envelope", {}).get(key, 0) for case in cases) for key in keys}


def _case_import_loss_rate(import_report: dict[str, Any] | None) -> float:
    if not import_report:
        return 0.0
    summary = import_report.get("summary", {})
    diagnostics = summary.get("invalidating_diagnostics", 0)
    records = summary.get("records", 0)
    return round(diagnostics / records, 6) if records else 0.0


def _aggregate_import_loss_rate(cases: list[dict[str, Any]]) -> float:
    records = sum(case.get("metrics", {}).get("memory_envelope", {}).get("import_records", 0) for case in cases)
    invalidating = 0
    for case in cases:
        report = case.get("import_diagnostics") or {}
        invalidating += report.get("summary", {}).get("invalidating_diagnostics", 0)
    return round(invalidating / records, 6) if records else 0.0


def _diagnosability_score_change(findings: list[dict[str, Any]]) -> float:
    diagnosability = [item for item in findings if item.get("category") in {"diagnosability", "scenario"}]
    return round(-0.05 * len(diagnosability), 6)


def _aggregate_label_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    labeled = [case["metrics"]["labels"] for case in cases if case.get("metrics", {}).get("labels")]
    expected = sum(item["expected"] for item in labeled)
    matched = sum(item["matched"] for item in labeled)
    unexpected = sum(len(item["unexpected"]) for item in labeled)
    precision = matched / (matched + unexpected) if matched or unexpected else 1.0
    recall = matched / expected if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"cases": len(labeled), "expected": expected, "matched": matched, "unexpected": unexpected, "precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6)}


def _top_remediations(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], Counter[str]] = defaultdict(Counter)
    for finding in findings:
        severity = str(finding.get("severity", "warning"))
        category = str(finding.get("category") or TAXONOMY.get(str(finding.get("code")), {}).get("category", "uncategorized"))
        owner = str(finding.get("service_owner") or TAXONOMY.get(str(finding.get("code")), {}).get("service_owner", "contract service owner"))
        remediation = str(finding.get("remediation") or TAXONOMY.get(str(finding.get("code")), {}).get("remediation", "Inspect the finding and update telemetry evidence."))
        effort = _estimated_effort(category, severity)
        benefit = _incident_readiness_benefit(category)
        groups[(severity, category, owner, effort, benefit)][remediation] += 1
    rows = []
    for (severity, category, owner, effort, benefit), remediations in groups.items():
        remediation, count = remediations.most_common(1)[0]
        rows.append({"severity": severity, "semantic_property": category, "affected_owner": owner, "estimated_effort": effort, "incident_readiness_benefit": benefit, "remediation": remediation, "findings": count})
    severity_rank = {"error": 0, "warning": 1, "info": 2}
    return sorted(rows, key=lambda item: (severity_rank.get(item["severity"], 9), -item["findings"], item["semantic_property"]))[:10]


def _estimated_effort(category: str, severity: str) -> str:
    if category in {"privacy-security", "preservation"} or severity == "error":
        return "medium"
    if category in {"schema", "contract"}:
        return "small"
    return "small-to-medium"


def _incident_readiness_benefit(category: str) -> str:
    mapping = {
        "diagnosability": "restores incident question evidence",
        "scenario": "restores incident question evidence",
        "privacy-security": "reduces sensitive telemetry exposure",
        "operability": "reduces noisy or costly telemetry",
        "static-coverage": "catches instrumentation gaps before runtime",
        "input": "bounds importer claim validity",
    }
    return mapping.get(category, "improves benchmark semantic coverage")


def _delta_metric(before: dict[str, Any], after: dict[str, Any], key: str) -> float:
    before_value = (before.get("labels") or {}).get(key, 0)
    after_value = (after.get("labels") or {}).get(key, 0)
    return round(after_value - before_value, 6)


def format_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    label_metrics = summary.get("label_metrics", {})
    lines = [
        f"# Benchmark: {summary['name']}",
        "",
        f"- Pass: `{str(summary['pass']).lower()}`",
        f"- Cases: {summary.get('cases', len(report.get('cases', [])))}",
        f"- Contracts: {summary['contracts']}",
        f"- Events: {summary['events']}",
        f"- Findings: {summary['findings']}",
        f"- Runtime: {summary['runtime_ms']} ms",
        f"- Runtime per K events: {summary.get('runtime_per_k_events_ms', 0)} ms",
        f"- Findings per K events: {summary.get('findings_per_k_events', 0)}",
        f"- Import loss rate: {summary.get('import_loss_rate', 0)}",
        f"- Label precision/recall/F1: {label_metrics.get('precision', 'n/a')} / {label_metrics.get('recall', 'n/a')} / {label_metrics.get('f1', 'n/a')}",
        f"- Findings by code: `{json.dumps(summary['findings_by_code'], sort_keys=True)}`",
        f"- Findings by severity: `{json.dumps(summary['findings_by_severity'], sort_keys=True)}`",
        "",
        "| Case | Tags | Checks | Pass | Events | Findings | Validation pass | Label precision | Label recall | Label F1 | Runtime ms | Findings/K events | Import loss |",
        "| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in report["cases"]:
        metrics = case["metrics"]
        labels = metrics.get("labels") or {}
        precision = labels.get("precision", "n/a")
        recall = labels.get("recall", "n/a")
        f1 = labels.get("f1", "n/a")
        checks = ",".join(name for name, enabled in case.get("checks", {}).items() if enabled) or "none"
        tags = ",".join(case.get("tags", [])) or "none"
        lines.append(
            f"| {case['id']} | {tags} | {checks} | `{str(case['pass']).lower()}` | {metrics['events']} | {metrics['findings']} | "
            f"`{str(metrics['validation_pass']).lower()}` | {precision} | {recall} | {f1} | {metrics['runtime_ms']} | "
            f"{metrics.get('findings_per_k_events', 0)} | {metrics.get('import_loss_rate', 0)} |"
        )
    if summary.get("top_remediations"):
        lines.extend(["", "## Top remediations", "", "| Severity | Semantic property | Owner | Effort | Benefit | Findings | Remediation |", "| --- | --- | --- | --- | --- | ---: | --- |"])
        for item in summary["top_remediations"]:
            lines.append(f"| {item['severity']} | {item['semantic_property']} | {item['affected_owner']} | {item['estimated_effort']} | {item['incident_readiness_benefit']} | {item['findings']} | {item['remediation']} |")
    lines.append("")
    return "\n".join(lines)
