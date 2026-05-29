from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Severity = Literal["info", "warning", "error"]

TAXONOMY: dict[str, dict[str, str]] = {
    "contract.version": {"category": "contract", "remediation": "Declare contract version 1.0."},
    "contract.service": {"category": "contract", "remediation": "Add a non-empty service name."},
    "contract.section_type": {"category": "contract", "remediation": "Use arrays for spans, metrics, and logs sections."},
    "contract.signal_type": {"category": "contract", "remediation": "Describe each signal as an object."},
    "contract.signal_name": {"category": "contract", "remediation": "Give each signal a stable telemetry name."},
    "contract.required_type": {"category": "contract", "remediation": "Use a boolean for required flags."},
    "contract.field_type": {"category": "contract", "remediation": "Use one of string, integer, number, boolean, object, array, or null."},
    "contract.allowed_values_type": {"category": "contract", "remediation": "Declare allowed_values as an array."},
    "contract.numeric_bound_type": {"category": "contract", "remediation": "Declare min and max bounds as numbers."},
    "contract.numeric_bounds": {"category": "contract", "remediation": "Ensure min is less than or equal to max."},
    "contract.forbidden_patterns_type": {"category": "contract", "remediation": "Declare forbidden_patterns as a string, object, or array of strings/objects."},
    "contract.invalid_regex": {"category": "contract", "remediation": "Fix the regular expression in the contract."},
    "contract.schema": {"category": "contract", "remediation": "Update the contract so it conforms to docs/contract.schema.json."},
    "contract.sensitive_field_unclassified": {"category": "schema", "remediation": "Classify sensitive fields with sensitivity and forbid raw-secret patterns."},
    "contract.conditional_requirement": {"category": "contract", "remediation": "Declare conditional requirements with an if field condition and then fields list."},
    "contract.severity_policy": {"category": "contract", "remediation": "Use a known log severity threshold such as WARN, ERROR, or FATAL."},
    "contract.duplicate_signal": {"category": "contract", "remediation": "Keep one contract definition per signal name and kind."},
    "contract.duplicate_field": {"category": "contract", "remediation": "Declare each field name in only one of fields, attributes, or tags for a signal."},
    "contract.policy_stub": {"category": "contract", "remediation": "Declare sampling and retention policy stubs with machine-readable rates, strategies, and day counts."},
    "contract.privacy_policy": {"category": "privacy-security", "remediation": "Declare a known privacy classification and an allowed transformation such as redacted, hashed, tokenized, bucketed, or omitted."},
    "contract.unit": {"category": "schema", "remediation": "Use a supported unit such as ms, bytes, percent, count, timestamp_ms, or usd."},
    "telemetry.missing_signal": {"category": "diagnosability", "remediation": "Emit the required span, metric, or log on the exercised path."},
    "telemetry.missing_field": {"category": "diagnosability", "remediation": "Attach the required attribute/tag/field to the signal."},
    "telemetry.field_type": {"category": "schema", "remediation": "Emit the field using the contract's declared primitive type."},
    "telemetry.allowed_values": {"category": "schema", "remediation": "Normalize the field to one of the declared allowed values."},
    "telemetry.pattern": {"category": "schema", "remediation": "Normalize the field so it matches the declared pattern."},
    "telemetry.pattern_type": {"category": "schema", "remediation": "Emit a string value when a regex pattern is required."},
    "telemetry.numeric_min": {"category": "schema", "remediation": "Investigate or clamp values below the declared minimum."},
    "telemetry.numeric_max": {"category": "schema", "remediation": "Investigate or clamp values above the declared maximum."},
    "telemetry.log_message": {"category": "diagnosability", "remediation": "Use a stable log message or event name matching the contract."},
    "telemetry.log_severity": {"category": "diagnosability", "remediation": "Emit the log at the severity required for alerting and search."},
    "telemetry.cardinality": {"category": "operability", "remediation": "Bucket, hash, drop, or bound labels with excessive cardinality."},
    "telemetry.cardinality_policy": {"category": "operability", "remediation": "Declare a max cardinality or explicitly allow unbounded values."},
    "telemetry.forbidden_pattern": {"category": "privacy-security", "remediation": "Redact, hash, or omit values matching forbidden sensitive patterns."},
    "telemetry.sensitive_value": {"category": "privacy-security", "remediation": "Do not emit raw PII, credentials, or bearer tokens in telemetry."},
    "telemetry.sensitive_unclassified": {"category": "privacy-security", "remediation": "Classify the field sensitivity and redact or hash the emitted value."},
    "telemetry.correlation_missing": {"category": "diagnosability", "remediation": "Emit a trace_id, span_id, request_id, or configured correlation key on correlated signals."},
    "telemetry.correlation_mismatch": {"category": "diagnosability", "remediation": "Propagate at least one shared correlation key value across the required signal kinds."},
    "telemetry.conditional_missing_field": {"category": "diagnosability", "remediation": "When the triggering field is present, emit all fields required by the conditional requirement."},
    "telemetry.log_severity_min": {"category": "diagnosability", "remediation": "Raise the emitted log severity to meet the contract's minimum severity policy."},
    "telemetry.privacy_transformation": {"category": "privacy-security", "remediation": "Emit the field using the transformation required by the contract privacy policy."},
    "telemetry.unit": {"category": "schema", "remediation": "Emit a value that satisfies the field's declared unit constraints."},
    "static.missing_instrumentation": {"category": "static-coverage", "remediation": "Add source instrumentation with the expected stable telemetry name."},
    "static.no_sources": {"category": "static-coverage", "remediation": "Pass source files or directories to the static checker."},
    "static.secret_logging": {"category": "privacy-security", "remediation": "Remove the sensitive value from logs or log only a redacted/hash surrogate."},
    "static.missing_correlation": {"category": "diagnosability", "remediation": "Include a trace_id, request_id, or configured correlation field in error logs."},
    "static.unbounded_label": {"category": "operability", "remediation": "Avoid user-controlled/high-cardinality metric labels or add bucketing."},
    "scenario.not_found": {"category": "scenario", "remediation": "Add or select a scenario that matches the incident question."},
    "scenario.requirement_type": {"category": "scenario", "remediation": "Describe scenario requirements as objects."},
    "scenario.missing_signal": {"category": "diagnosability", "remediation": "Emit the signal needed to answer the scenario question."},
    "scenario.missing_field": {"category": "diagnosability", "remediation": "Emit the field needed to answer the scenario question."},
    "input.load_error": {"category": "input", "remediation": "Fix the referenced input path or file format."},
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
        if taxonomy.get("remediation"):
            item.setdefault("remediation", taxonomy["remediation"])
        return item


SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "error": 2}


def has_at_least(findings: list[Finding], severity: str) -> bool:
    threshold = SEVERITY_ORDER[severity]
    return any(SEVERITY_ORDER[item.severity] >= threshold for item in findings)
