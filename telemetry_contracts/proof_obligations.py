from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from .benchmark import run_benchmark
from .core_semantics import evaluate_contract_semantics
from .findings import TAXONOMY, Finding
from .preservation import check_transformation_preservation
from .validator import _strict_enabled, validate_contract_shape, validate_events


PROOF_OBLIGATION_MODEL = {
    "name": "telemetry-contract-proof-obligations-v1",
    "relation": (
        "A proof obligation is an executable template tying one telemetry-contract feature "
        "to a formal clause, premises, a desired conclusion, and repository evidence that can "
        "discharge or violate it on finite artifacts. These templates are not independent "
        "machine-checked proofs; they are reproducible proof goals and evidence links for "
        "well-formedness, satisfaction, preservation, refinement, monitor soundness, and "
        "benchmark-label validity."
    ),
    "families": [
        "well-formedness",
        "satisfaction",
        "preservation",
        "refinement",
        "monitor-soundness",
        "benchmark-label-validity",
    ],
}


FEATURE_CATALOG = [
    {"feature": "contract header", "clauses": ["WF.schema", "WF.version", "WF.service"], "families": ["well-formedness"]},
    {"feature": "signal declarations", "clauses": ["WF.signal-section", "WF.signal-object", "WF.signal-name", "WF.unique-signal", "WF.unique-field"], "families": ["well-formedness", "satisfaction", "refinement"]},
    {"feature": "required signals", "clauses": ["SAT.required-signal"], "families": ["satisfaction", "preservation", "monitor-soundness", "refinement"]},
    {"feature": "field predicates", "clauses": ["WF.field-type", "WF.required-boolean", "SAT.required-field", "SAT.field-type"], "families": ["well-formedness", "satisfaction", "preservation", "monitor-soundness", "refinement"]},
    {"feature": "allowed values", "clauses": ["WF.allowed-values", "SAT.allowed-values"], "families": ["well-formedness", "satisfaction", "refinement"]},
    {"feature": "regex patterns", "clauses": ["WF.regex", "SAT.regex", "SAT.regex-domain"], "families": ["well-formedness", "satisfaction", "refinement"]},
    {"feature": "forbidden patterns and sensitive values", "clauses": ["WF.forbidden-pattern", "SAT.forbidden-pattern", "SAT.raw-sensitive-value"], "families": ["well-formedness", "satisfaction", "preservation", "refinement"]},
    {"feature": "numeric bounds", "clauses": ["WF.numeric-bound", "WF.numeric-interval", "SAT.numeric-lower-bound", "SAT.numeric-upper-bound"], "families": ["well-formedness", "satisfaction", "refinement"]},
    {"feature": "units", "clauses": ["WF.unit", "SAT.unit"], "families": ["well-formedness", "satisfaction", "refinement"]},
    {"feature": "privacy classifications", "clauses": ["WF.privacy-classification", "WF.privacy-policy", "SAT.privacy-preservation", "SAT.sensitive-classification"], "families": ["well-formedness", "satisfaction", "preservation", "refinement"]},
    {"feature": "policy stubs", "clauses": ["WF.policy-stub"], "families": ["well-formedness", "preservation", "refinement"]},
    {"feature": "field definitions", "clauses": ["WF.field-definitions", "WF.field-reference", "WF.field-reference-acyclic"], "families": ["well-formedness", "satisfaction", "refinement"]},
    {"feature": "conditional requirements", "clauses": ["WF.conditional", "SAT.conditional-obligation"], "families": ["well-formedness", "satisfaction", "monitor-soundness", "refinement"]},
    {"feature": "log severity and message policies", "clauses": ["WF.severity-policy", "SAT.log-message", "SAT.log-severity", "SAT.log-severity-threshold"], "families": ["well-formedness", "satisfaction", "monitor-soundness", "refinement"]},
    {"feature": "cardinality policies", "clauses": ["SAT.cardinality-bound", "SAT.cardinality-policy"], "families": ["satisfaction", "preservation", "refinement"]},
    {"feature": "correlation policies", "clauses": ["SAT.correlation-presence", "SAT.correlation-intersection"], "families": ["well-formedness", "satisfaction", "monitor-soundness", "refinement"]},
    {"feature": "temporal sequences", "clauses": ["WF.temporal-sequence", "SAT.temporal-presence", "SAT.temporal-window"], "families": ["well-formedness", "satisfaction", "monitor-soundness", "refinement"]},
    {"feature": "temporal logic properties", "clauses": ["WF.temporal-property", "SAT.temporal-safety", "SAT.temporal-absence", "SAT.temporal-response", "SAT.temporal-order", "SAT.temporal-deadline"], "families": ["well-formedness", "satisfaction", "monitor-soundness", "refinement"]},
    {"feature": "alternative obligations", "clauses": ["WF.alternative-obligation", "SAT.alternative-disjunction", "ADEQ.alternative-observation"], "families": ["well-formedness", "satisfaction", "preservation", "refinement"]},
    {"feature": "strict closed world", "clauses": ["WF.strict-policy", "STRICT.service-closed-world", "STRICT.signal-closed-world", "STRICT.field-closed-world", "STRICT.transformation-documented"], "families": ["well-formedness", "satisfaction", "preservation", "refinement"]},
    {"feature": "scenario adequacy", "clauses": ["SCENARIO.selection", "SCENARIO.requirement-wf", "ADEQ.required-signal", "ADEQ.required-field"], "families": ["satisfaction", "preservation", "monitor-soundness", "refinement"]},
    {"feature": "transformation preservation", "clauses": ["PRES.runtime-obligation", "PRES.adequacy-signal", "PRES.adequacy-field"], "families": ["preservation"]},
    {"feature": "static instrumentation evidence", "clauses": ["STATIC.signal-literal", "STATIC.source-domain", "STATIC.raw-sensitive-log", "STATIC.correlation-evidence", "STATIC.cardinality-risk"], "families": ["satisfaction", "monitor-soundness", "benchmark-label-validity"]},
    {"feature": "benchmark labels", "clauses": ["BENCH.label-validity"], "families": ["benchmark-label-validity"]},
    {"feature": "contract refinement", "clauses": ["REF.requirement-preservation", "REF.privacy-nonweakening", "REF.assumption-compatibility"], "families": ["refinement"]},
]


def generate_proof_obligations_report(
    contract: dict[str, Any],
    events: list[dict[str, Any]] | None = None,
    *,
    strict: bool | None = None,
    source_events: list[dict[str, Any]] | None = None,
    transformed_events: list[dict[str, Any]] | None = None,
    benchmark_config: str | None = None,
) -> dict[str, Any]:
    """Instantiate proof-obligation templates against available artifacts."""
    wf_findings = validate_contract_shape(contract)
    runtime_findings = validate_events(contract, events, strict=strict) if events is not None else []
    semantics_report = evaluate_contract_semantics(contract, events, strict=strict) if events is not None else None
    preservation_report = (
        check_transformation_preservation(contract, source_events, transformed_events)
        if source_events is not None and transformed_events is not None
        else None
    )
    benchmark_report = run_benchmark(benchmark_config) if benchmark_config else None

    obligations: list[dict[str, Any]] = []
    obligations.extend(_well_formedness_obligations(contract, wf_findings))
    obligations.extend(_satisfaction_obligations(contract, events, runtime_findings, strict))
    obligations.extend(_preservation_obligations(contract, preservation_report))
    obligations.extend(_refinement_obligations(contract))
    obligations.extend(_monitor_soundness_obligations(contract, semantics_report, strict))
    obligations.extend(_benchmark_label_obligations(benchmark_report, benchmark_config))

    status_counts = Counter(item["status"] for item in obligations)
    family_counts = Counter(item["family"] for item in obligations)
    return {
        "model": PROOF_OBLIGATION_MODEL,
        "service": contract.get("service", ""),
        "summary": {
            "features_cataloged": len(FEATURE_CATALOG),
            "obligations": len(obligations),
            "status_counts": dict(sorted(status_counts.items())),
            "family_counts": dict(sorted(family_counts.items())),
            "discharged": status_counts.get("discharged", 0),
            "violated": status_counts.get("violated", 0),
            "pending": status_counts.get("pending", 0),
            "events": len(events) if events is not None else None,
            "strict": _strict_enabled(contract, strict),
        },
        "feature_catalog": FEATURE_CATALOG,
        "obligations": obligations,
        "limitations": [
            "Templates are executable proof goals with finite evidence links, not an independently verified theorem-prover development.",
            "Refinement obligations are templates until a dedicated refinement checker is supplied in a future roadmap step.",
            "Monitor-soundness evidence is bounded to deterministic checker and small-step semantic alignment on supplied finite traces.",
            "Benchmark-label validity describes checked-in labels and reports; it is not a universal precision/recall claim.",
        ],
    }


def format_proof_obligations_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Proof-obligation report: {report.get('service', '')}",
        "",
        f"- Model: `{report['model']['name']}`",
        f"- Features cataloged: {summary['features_cataloged']}",
        f"- Obligations: {summary['obligations']}",
        f"- Discharged: {summary['discharged']}",
        f"- Violated: {summary['violated']}",
        f"- Pending templates: {summary['pending']}",
        f"- Status counts: `{json.dumps(summary['status_counts'], sort_keys=True)}`",
        f"- Family counts: `{json.dumps(summary['family_counts'], sort_keys=True)}`",
        f"- Events: {summary['events'] if summary['events'] is not None else 'not supplied'}",
        f"- Strict mode: `{str(summary['strict']).lower()}`",
        "",
        "## Relation",
        "",
        report["model"]["relation"],
        "",
        "## Obligations",
        "",
    ]
    for family in report["model"]["families"]:
        family_items = [item for item in report["obligations"] if item["family"] == family]
        lines.extend([f"### {family}", ""])
        if not family_items:
            lines.append("No obligations instantiated for supplied artifacts.")
        for item in family_items:
            lines.append(f"- **{item['id']}** `{item['status']}` — {item['feature']} / `{item['formal_clause']}`")
            lines.append(f"  - Template: {item['template']}")
            lines.append(f"  - Evidence: {item['evidence']}")
            if item.get("findings"):
                codes = Counter(finding["code"] for finding in item["findings"])
                lines.append(f"  - Finding codes: `{json.dumps(dict(sorted(codes.items())), sort_keys=True)}`")
        lines.append("")
    lines.extend(["## Feature catalog", ""])
    for item in report["feature_catalog"]:
        lines.append(f"- **{item['feature']}** — clauses `{', '.join(item['clauses'])}`; families `{', '.join(item['families'])}`")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines).rstrip()


def _well_formedness_obligations(contract: dict[str, Any], wf_findings: list[Finding]) -> list[dict[str, Any]]:
    by_clause = _findings_by_clause(wf_findings)
    clauses = sorted({clause for item in FEATURE_CATALOG for clause in item["clauses"] if clause.startswith("WF.")})
    obligations = []
    for clause in clauses:
        feature = _feature_for_clause(clause)
        findings = by_clause.get(clause, [])
        obligations.append(
            _obligation(
                "well-formedness",
                feature,
                clause,
                f"If contract service `{contract.get('service', '')}` uses {feature}, every syntax premise for {clause} is decidable before telemetry is read.",
                "validate_contract_shape",
                findings,
                pending=False,
            )
        )
    return obligations


def _satisfaction_obligations(contract: dict[str, Any], events: list[dict[str, Any]] | None, findings: list[Finding], strict: bool | None) -> list[dict[str, Any]]:
    by_clause = _findings_by_clause(findings)
    features = _present_features(contract)
    obligations = []
    for clause in sorted(_satisfaction_clauses(features, _strict_enabled(contract, strict))):
        obligations.append(
            _obligation(
                "satisfaction",
                _feature_for_clause(clause),
                clause,
                "For finite trace T and contract C, all witnesses required by this clause exist and satisfy declared predicates.",
                f"validate_events over {len(events) if events is not None else 'no'} supplied events",
                by_clause.get(clause, []),
                pending=events is None,
            )
        )
    return obligations


def _preservation_obligations(contract: dict[str, Any], preservation_report: dict[str, Any] | None) -> list[dict[str, Any]]:
    clauses = ["PRES.runtime-obligation", "PRES.adequacy-signal", "PRES.adequacy-field"]
    if _present_features(contract).get("privacy classifications"):
        clauses.append("SAT.privacy-preservation")
    findings_by_clause: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if preservation_report is not None:
        for finding in preservation_report.get("findings", []):
            findings_by_clause[str(finding.get("formal_clause", ""))].append(finding)
    return [
        _obligation_dict(
            "preservation",
            _feature_for_clause(clause),
            clause,
            "If source trace T satisfies an obligation and approved transformation Δ produces T′, then T′ preserves the same obligation-local evidence.",
            "check_transformation_preservation" if preservation_report is not None else "source/transformed traces not supplied",
            findings_by_clause.get(clause, []),
            pending=preservation_report is None,
        )
        for clause in clauses
    ]


def _refinement_obligations(contract: dict[str, Any]) -> list[dict[str, Any]]:
    present = _present_features(contract)
    clauses = ["REF.requirement-preservation", "REF.privacy-nonweakening", "REF.assumption-compatibility"]
    return [
        _obligation_dict(
            "refinement",
            "contract refinement",
            clause,
            "For base contract C and candidate C′, every required evidence obligation is preserved, privacy obligations are not weakened, and assumptions are compatible.",
            f"template instantiated for service `{contract.get('service', '')}` with features {', '.join(sorted(present)) or 'contract header'}",
            [],
            pending=True,
        )
        for clause in clauses
    ]


def _monitor_soundness_obligations(contract: dict[str, Any], semantics_report: dict[str, Any] | None, strict: bool | None) -> list[dict[str, Any]]:
    present = _present_features(contract)
    clauses = sorted(_satisfaction_clauses(present, _strict_enabled(contract, strict)))
    status_pending = semantics_report is None
    aligned = bool(semantics_report and semantics_report["summary"].get("aligned_with_checker"))
    findings = [] if aligned else [{"code": "semantics.alignment", "formal_clause": "MON.soundness", "message": "small-step denotation did not align with deterministic checker"}]
    return [
        _obligation_dict(
            "monitor-soundness",
            _feature_for_clause(clause),
            f"MON.soundness.{clause}",
            "A bounded monitor for this clause is sound when each emitted violation corresponds to a violated semantic obligation in the small-step denotation.",
            "evaluate_contract_semantics alignment" if semantics_report is not None else "events not supplied",
            findings,
            pending=status_pending,
        )
        for clause in clauses
    ]


def _benchmark_label_obligations(benchmark_report: dict[str, Any] | None, benchmark_config: str | None) -> list[dict[str, Any]]:
    if benchmark_report is None:
        return [
            _obligation_dict(
                "benchmark-label-validity",
                "benchmark labels",
                "BENCH.label-validity",
                "Every expected label is matched by one finding, and every produced finding is either labeled or explicitly outside the benchmark claim.",
                "benchmark config not supplied",
                [],
                pending=True,
            )
        ]
    findings = []
    for case in benchmark_report.get("cases", []):
        labels = case.get("metrics", {}).get("labels")
        if labels and not labels.get("pass"):
            findings.append({"code": "benchmark.label_mismatch", "formal_clause": "BENCH.label-validity", "message": f"case {case.get('id')} labels did not match"})
    return [
        _obligation_dict(
            "benchmark-label-validity",
            "benchmark labels",
            "BENCH.label-validity",
            "Every expected label is matched by one finding, and every produced finding is either labeled or explicitly outside the benchmark claim.",
            f"run_benchmark({benchmark_config}) pass={benchmark_report['summary']['pass']}",
            findings,
            pending=False,
        )
    ]


def _obligation(family: str, feature: str, clause: str, template: str, evidence: str, findings: list[Finding], *, pending: bool) -> dict[str, Any]:
    return _obligation_dict(family, feature, clause, template, evidence, [finding.to_dict() for finding in findings], pending=pending)


def _obligation_dict(family: str, feature: str, clause: str, template: str, evidence: str, findings: list[dict[str, Any]], *, pending: bool) -> dict[str, Any]:
    if pending:
        status = "pending"
    elif findings:
        status = "violated"
    else:
        status = "discharged"
    return {
        "id": f"{family}:{clause}",
        "family": family,
        "feature": feature,
        "formal_clause": clause,
        "template": template,
        "evidence": evidence,
        "status": status,
        "findings": findings,
    }


def _findings_by_clause(findings: list[Finding]) -> dict[str, list[Finding]]:
    by_clause: dict[str, list[Finding]] = defaultdict(list)
    for finding in findings:
        clause = TAXONOMY.get(finding.code, {}).get("formal_clause")
        if clause:
            by_clause[str(clause)].append(finding)
    return by_clause


def _feature_for_clause(clause: str) -> str:
    for item in FEATURE_CATALOG:
        if clause in item["clauses"]:
            return str(item["feature"])
    if clause.startswith("MON.soundness."):
        return _feature_for_clause(clause.removeprefix("MON.soundness."))
    return "contract feature"


def _present_features(contract: dict[str, Any]) -> dict[str, bool]:
    features = {"contract header": True}
    if any(isinstance(contract.get(section), list) and contract.get(section) for section in ("spans", "metrics", "logs")):
        features["signal declarations"] = True
        features["required signals"] = True
        features["field predicates"] = True
    if isinstance(contract.get("field_definitions"), dict) and contract["field_definitions"]:
        features["field definitions"] = True
    if isinstance(contract.get("privacy_classifications"), dict) and contract["privacy_classifications"]:
        features["privacy classifications"] = True
    if isinstance(contract.get("metadata"), dict) and any(key in contract["metadata"] for key in ("sampling", "retention")):
        features["policy stubs"] = True
    if isinstance(contract.get("correlation"), dict):
        features["correlation policies"] = True
    if isinstance(contract.get("temporal_sequences"), list) and contract["temporal_sequences"]:
        features["temporal sequences"] = True
    if isinstance(contract.get("temporal_properties"), list) and contract["temporal_properties"]:
        features["temporal logic properties"] = True
    if isinstance(contract.get("alternative_obligations"), list) and contract["alternative_obligations"]:
        features["alternative obligations"] = True
    if _strict_enabled(contract, None):
        features["strict closed world"] = True
    if isinstance(contract.get("scenarios"), list) and contract["scenarios"]:
        features["scenario adequacy"] = True
    if isinstance(contract.get("metadata"), dict) and isinstance(contract["metadata"].get("transformation_preservation"), dict):
        features["transformation preservation"] = True
    for spec in _signal_specs(contract):
        fields = _field_like_specs(spec)
        if any("allowed_values" in field for field in fields):
            features["allowed values"] = True
        if any("pattern" in field or "message_pattern" in spec for field in fields):
            features["regex patterns"] = True
        if any("forbidden_patterns" in field for field in fields):
            features["forbidden patterns and sensitive values"] = True
        if any("min" in field or "max" in field for field in fields):
            features["numeric bounds"] = True
        if any("unit" in field for field in fields):
            features["units"] = True
        if any("classification" in field or "sensitivity" in field or "transformation" in field for field in fields):
            features["privacy classifications"] = True
        if spec.get("conditional_requirements"):
            features["conditional requirements"] = True
        if spec.get("severity") or spec.get("severity_policy") or spec.get("message_pattern"):
            features["log severity and message policies"] = True
        if any("max_cardinality" in field or "cardinality" in field for field in fields):
            features["cardinality policies"] = True
    return features


def _satisfaction_clauses(features: dict[str, bool], strict_enabled: bool) -> set[str]:
    clauses = {"SAT.required-signal", "SAT.required-field", "SAT.field-type"}
    feature_to_clauses = {
        "allowed values": {"SAT.allowed-values"},
        "regex patterns": {"SAT.regex", "SAT.regex-domain"},
        "forbidden patterns and sensitive values": {"SAT.forbidden-pattern", "SAT.raw-sensitive-value"},
        "numeric bounds": {"SAT.numeric-lower-bound", "SAT.numeric-upper-bound"},
        "units": {"SAT.unit"},
        "privacy classifications": {"SAT.privacy-preservation", "SAT.sensitive-classification"},
        "conditional requirements": {"SAT.conditional-obligation"},
        "log severity and message policies": {"SAT.log-message", "SAT.log-severity", "SAT.log-severity-threshold"},
        "cardinality policies": {"SAT.cardinality-bound", "SAT.cardinality-policy"},
        "correlation policies": {"SAT.correlation-presence", "SAT.correlation-intersection"},
        "temporal sequences": {"SAT.temporal-presence", "SAT.temporal-window"},
        "temporal logic properties": {"SAT.temporal-safety", "SAT.temporal-absence", "SAT.temporal-response", "SAT.temporal-order", "SAT.temporal-deadline"},
        "alternative obligations": {"SAT.alternative-disjunction"},
        "scenario adequacy": {"ADEQ.required-signal", "ADEQ.required-field", "ADEQ.alternative-observation"},
    }
    for feature, feature_clauses in feature_to_clauses.items():
        if features.get(feature):
            clauses.update(feature_clauses)
    if strict_enabled or features.get("strict closed world"):
        clauses.update({"STRICT.service-closed-world", "STRICT.signal-closed-world", "STRICT.field-closed-world", "STRICT.transformation-documented"})
    return clauses


def _signal_specs(contract: dict[str, Any]) -> list[dict[str, Any]]:
    specs = []
    for section in ("spans", "metrics", "logs"):
        raw = contract.get(section, []) or []
        if isinstance(raw, list):
            specs.extend(item for item in raw if isinstance(item, dict))
    return specs


def _field_like_specs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for container in ("fields", "attributes", "tags"):
        raw = spec.get(container, {}) or {}
        if isinstance(raw, dict):
            fields.extend(item for item in raw.values() if isinstance(item, dict))
    if isinstance(spec.get("value"), dict):
        fields.append(spec["value"])
    return fields
