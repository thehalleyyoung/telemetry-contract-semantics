from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Severity = Literal["info", "warning", "error"]


def _entry(
    category: str,
    remediation: str,
    formal_clause: str,
    default_severity: str = "error",
    disclosure_sensitivity: str = "internal",
    service_owner: str = "contract service owner",
) -> dict[str, Any]:
    sarif_level = {"error": "error", "warning": "warning", "info": "note"}[default_severity]
    return {
        "category": category,
        "default_severity": default_severity,
        "formal_clause": formal_clause,
        "remediation": remediation,
        "disclosure_sensitivity": disclosure_sensitivity,
        "service_owner": service_owner,
        "sarif_level": sarif_level,
        "ci": {
            "default_fail_on": default_severity,
            "sarif_level": sarif_level,
            "baseline_key_fields": ["code", "path", "contract_path", "event_index"],
        },
    }


TAXONOMY: dict[str, dict[str, Any]] = {
    "contract.version": _entry("contract", "Declare contract version 1.0.", "WF.version"),
    "contract.service": _entry("contract", "Add a non-empty service name.", "WF.service"),
    "contract.section_type": _entry("contract", "Use arrays for spans, metrics, and logs sections.", "WF.signal-section"),
    "contract.signal_type": _entry("contract", "Describe each signal as an object.", "WF.signal-object"),
    "contract.signal_name": _entry("contract", "Give each signal a stable telemetry name.", "WF.signal-name"),
    "contract.required_type": _entry("contract", "Use a boolean for required flags.", "WF.required-boolean"),
    "contract.field_type": _entry("contract", "Use one of string, integer, number, boolean, object, array, or null.", "WF.field-type"),
    "contract.allowed_values_type": _entry("contract", "Declare allowed_values as an array.", "WF.allowed-values"),
    "contract.numeric_bound_type": _entry("contract", "Declare min and max bounds as numbers.", "WF.numeric-bound"),
    "contract.numeric_bounds": _entry("contract", "Ensure min is less than or equal to max.", "WF.numeric-interval"),
    "contract.forbidden_patterns_type": _entry("contract", "Declare forbidden_patterns as a string, object, or array of strings/objects.", "WF.forbidden-pattern"),
    "contract.invalid_regex": _entry("contract", "Fix the regular expression in the contract.", "WF.regex"),
    "contract.schema": _entry("contract", "Update the contract so it conforms to docs/contract.schema.json.", "WF.schema"),
    "contract.sensitive_field_unclassified": _entry("schema", "Classify sensitive fields with sensitivity and forbid raw-secret patterns.", "WF.privacy-classification", "warning"),
    "contract.conditional_requirement": _entry("contract", "Declare conditional requirements with an if field condition and then fields list.", "WF.conditional"),
    "contract.severity_policy": _entry("contract", "Use a known log severity threshold such as WARN, ERROR, or FATAL.", "WF.severity-policy"),
    "contract.duplicate_signal": _entry("contract", "Keep one contract definition per signal name and kind.", "WF.unique-signal"),
    "contract.duplicate_field": _entry("contract", "Declare each field name in only one of fields, attributes, or tags for a signal.", "WF.unique-field"),
    "contract.policy_stub": _entry("contract", "Declare sampling and retention policy stubs with machine-readable rates, strategies, and day counts.", "WF.policy-stub"),
    "contract.privacy_policy": _entry("privacy-security", "Declare a known privacy classification and an allowed transformation such as redacted, hashed, tokenized, bucketed, or omitted.", "WF.privacy-policy", disclosure_sensitivity="responsible-disclosure"),
    "contract.unit": _entry("schema", "Use a supported unit such as ms, bytes, percent, count, timestamp_ms, or usd.", "WF.unit"),
    "contract.field_definitions": _entry("contract", "Declare reusable field definitions as an object of field specs.", "WF.field-definitions"),
    "contract.field_ref": _entry("contract", "Reference an existing field definition or inline the field spec.", "WF.field-reference"),
    "contract.field_ref_cycle": _entry("contract", "Remove cyclic field-definition references.", "WF.field-reference-acyclic"),
    "contract.temporal_sequence": _entry("contract", "Declare temporal sequences with valid steps, kinds, group_by keys, and positive windows.", "WF.temporal-sequence"),
    "telemetry.missing_signal": _entry("diagnosability", "Emit the required span, metric, or log on the exercised path.", "SAT.required-signal"),
    "telemetry.missing_field": _entry("diagnosability", "Attach the required attribute/tag/field to the signal.", "SAT.required-field"),
    "telemetry.field_type": _entry("schema", "Emit the field using the contract's declared primitive type.", "SAT.field-type"),
    "telemetry.allowed_values": _entry("schema", "Normalize the field to one of the declared allowed values.", "SAT.allowed-values"),
    "telemetry.pattern": _entry("schema", "Normalize the field so it matches the declared pattern.", "SAT.regex"),
    "telemetry.pattern_type": _entry("schema", "Emit a string value when a regex pattern is required.", "SAT.regex-domain"),
    "telemetry.numeric_min": _entry("schema", "Investigate or clamp values below the declared minimum.", "SAT.numeric-lower-bound"),
    "telemetry.numeric_max": _entry("schema", "Investigate or clamp values above the declared maximum.", "SAT.numeric-upper-bound"),
    "telemetry.log_message": _entry("diagnosability", "Use a stable log message or event name matching the contract.", "SAT.log-message"),
    "telemetry.log_severity": _entry("diagnosability", "Emit the log at the severity required for alerting and search.", "SAT.log-severity"),
    "telemetry.cardinality": _entry("operability", "Bucket, hash, drop, or bound labels with excessive cardinality.", "SAT.cardinality-bound", "warning"),
    "telemetry.cardinality_policy": _entry("operability", "Declare a max cardinality or explicitly allow unbounded values.", "SAT.cardinality-policy", "warning"),
    "telemetry.forbidden_pattern": _entry("privacy-security", "Redact, hash, or omit values matching forbidden sensitive patterns.", "SAT.forbidden-pattern", disclosure_sensitivity="responsible-disclosure"),
    "telemetry.sensitive_value": _entry("privacy-security", "Do not emit raw PII, credentials, or bearer tokens in telemetry.", "SAT.raw-sensitive-value", disclosure_sensitivity="responsible-disclosure"),
    "telemetry.sensitive_unclassified": _entry("privacy-security", "Classify the field sensitivity and redact or hash the emitted value.", "SAT.sensitive-classification", "warning", "responsible-disclosure"),
    "telemetry.correlation_missing": _entry("diagnosability", "Emit a trace_id, span_id, request_id, or configured correlation key on correlated signals.", "SAT.correlation-presence"),
    "telemetry.correlation_mismatch": _entry("diagnosability", "Propagate at least one shared correlation key value across the required signal kinds.", "SAT.correlation-intersection"),
    "telemetry.conditional_missing_field": _entry("diagnosability", "When the triggering field is present, emit all fields required by the conditional requirement.", "SAT.conditional-obligation"),
    "telemetry.log_severity_min": _entry("diagnosability", "Raise the emitted log severity to meet the contract's minimum severity policy.", "SAT.log-severity-threshold"),
    "telemetry.privacy_transformation": _entry("privacy-security", "Emit the field using the transformation required by the contract privacy policy.", "SAT.privacy-preservation", disclosure_sensitivity="responsible-disclosure"),
    "telemetry.unit": _entry("schema", "Emit a value that satisfies the field's declared unit constraints.", "SAT.unit"),
    "telemetry.temporal_missing_step": _entry("diagnosability", "Emit every event required by the temporal sequence in the grouped incident window.", "SAT.temporal-presence"),
    "telemetry.temporal_window": _entry("diagnosability", "Emit the temporal sequence within the declared bounded window.", "SAT.temporal-window"),
    "static.missing_instrumentation": _entry("static-coverage", "Add source instrumentation with the expected stable telemetry name.", "STATIC.signal-literal"),
    "static.no_sources": _entry("static-coverage", "Pass source files or directories to the static checker.", "STATIC.source-domain"),
    "static.secret_logging": _entry("privacy-security", "Remove the sensitive value from logs or log only a redacted/hash surrogate.", "STATIC.raw-sensitive-log", disclosure_sensitivity="responsible-disclosure"),
    "static.missing_correlation": _entry("diagnosability", "Include a trace_id, request_id, or configured correlation field in error logs.", "STATIC.correlation-evidence"),
    "static.unbounded_label": _entry("operability", "Avoid user-controlled/high-cardinality metric labels or add bucketing.", "STATIC.cardinality-risk", "warning"),
    "scenario.not_found": _entry("scenario", "Add or select a scenario that matches the incident question.", "SCENARIO.selection"),
    "scenario.requirement_type": _entry("scenario", "Describe scenario requirements as objects.", "SCENARIO.requirement-wf"),
    "scenario.missing_signal": _entry("diagnosability", "Emit the signal needed to answer the scenario question.", "ADEQ.required-signal"),
    "scenario.missing_field": _entry("diagnosability", "Emit the field needed to answer the scenario question.", "ADEQ.required-field"),
    "preservation.contract_obligation": _entry("preservation", "Change or configure the transformation so transformed telemetry still satisfies obligations that held before transformation.", "PRES.runtime-obligation"),
    "preservation.scenario_signal": _entry("preservation", "Keep at least one transformed signal witness for each selected diagnosability requirement.", "PRES.adequacy-signal"),
    "preservation.scenario_field": _entry("preservation", "Keep the transformed field, or provide an approved surrogate that still answers the selected incident question.", "PRES.adequacy-field"),
    "input.load_error": _entry("input", "Fix the referenced input path or file format.", "INPUT.parse"),
}


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str
    path: str
    contract_path: str | None = None
    event_index: int | None = None
    details: dict[str, Any] | None = None
    category: str | None = None
    remediation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        item = {key: value for key, value in asdict(self).items() if value is not None}
        taxonomy = TAXONOMY.get(self.code, {})
        item.setdefault("category", taxonomy.get("category", "uncategorized"))
        for key in ("formal_clause", "remediation", "disclosure_sensitivity", "service_owner", "sarif_level", "ci"):
            if taxonomy.get(key):
                item.setdefault(key, taxonomy[key])
        return item


SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "error": 2}


def has_at_least(findings: list[Finding], severity: str) -> bool:
    threshold = SEVERITY_ORDER[severity]
    return any(SEVERITY_ORDER[item.severity] >= threshold for item in findings)
