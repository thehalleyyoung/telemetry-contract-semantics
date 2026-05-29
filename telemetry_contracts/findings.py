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
    "contract.temporal_property": _entry("contract", "Declare temporal properties with a valid type, selectors, predicates, grouping keys, and positive time bounds.", "WF.temporal-property"),
    "contract.hyperproperty": _entry("contract", "Declare hyperproperties with a valid type, witness fields, and pair/set quantification keys.", "WF.hyperproperty"),
    "contract.alternative_obligation": _entry("contract", "Declare each alternative obligation with an id and a non-empty any_of list of signal options.", "WF.alternative-obligation"),
    "contract.strict_policy": _entry("contract", "Declare strict-validation escape hatches as bounded service, signal, field, or transformation lists.", "WF.strict-policy"),
    "contract.assume_guarantee": _entry("contract", "Declare assume-guarantee obligations under service_guarantees, collector_assumptions, environment_assumptions, or oncall_obligations with concrete finite-trace evidence.", "WF.assume-guarantee"),
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
    "telemetry.temporal_order": _entry("diagnosability", "Emit telemetry in the order required by the temporal property or sequence.", "SAT.temporal-order"),
    "telemetry.temporal_window": _entry("diagnosability", "Emit the temporal sequence within the declared bounded window.", "SAT.temporal-window"),
    "telemetry.temporal_safety": _entry("diagnosability", "Keep every matched event inside the declared temporal invariant.", "SAT.temporal-safety"),
    "telemetry.temporal_absence": _entry("diagnosability", "Do not emit the forbidden event in traces covered by this absence property.", "SAT.temporal-absence"),
    "telemetry.temporal_response": _entry("diagnosability", "Emit the required response event inside the bounded response window after each trigger.", "SAT.temporal-response"),
    "telemetry.temporal_deadline": _entry("diagnosability", "Emit the deadline-bound event before the declared time budget expires.", "SAT.temporal-deadline"),
    "telemetry.hyper_pii_disclosure": _entry("privacy-security", "Redact, hash, tokenize, bucket, or omit sensitive values before they reach public telemetry sinks.", "HYP.pii-non-disclosure", disclosure_sensitivity="responsible-disclosure"),
    "telemetry.hyper_tenant_interference": _entry("privacy-security", "Do not allow telemetry for different tenants to share an isolation key such as trace_id, request_id, or session_id.", "HYP.tenant-non-interference", disclosure_sensitivity="responsible-disclosure"),
    "telemetry.alternative_missing": _entry("diagnosability", "Emit at least one of the declared alternative evidence options with its required fields.", "SAT.alternative-disjunction"),
    "telemetry.strict_unmodeled_service": _entry("schema", "Either emit telemetry for the modeled service or add a bounded allow_unmodeled_services escape hatch.", "STRICT.service-closed-world"),
    "telemetry.strict_undeclared_signal": _entry("schema", "Declare the emitted signal in spans, metrics, logs, scenarios, or alternative obligations, or add an explicit strict allow_undeclared_signals escape hatch.", "STRICT.signal-closed-world"),
    "telemetry.strict_unexpected_field": _entry("schema", "Declare the emitted field on the signal contract or add an explicit strict allowed_extra_fields escape hatch.", "STRICT.field-closed-world"),
    "telemetry.strict_undocumented_transformation": _entry("preservation", "Document the collector transformation under metadata.transformation_preservation.approved_transformations or strict allow_collector_transformations.", "STRICT.transformation-documented"),
    "semconv.missing_attribute": _entry("schema", "Add the cited OpenTelemetry semantic-convention attribute to the contract and emitted telemetry, or document an artifact-scoped local exception.", "SEMCONV.required-attribute", "warning"),
    "semconv.legacy_attribute": _entry("schema", "Rename the legacy attribute to the cited current OpenTelemetry semantic-convention attribute.", "SEMCONV.attribute-alias", "warning"),
    "semconv.signal_name": _entry("schema", "Rename the signal to the cited low-cardinality OpenTelemetry semantic-convention shape.", "SEMCONV.signal-name", "warning"),
    "semconv.metric_unit": _entry("schema", "Declare the metric unit explicitly and consider removing the unit-only suffix from the metric name.", "SEMCONV.metric-unit", "warning"),
    "semconv.local_policy": _entry("schema", "Satisfy the contract's metadata.semantic_conventions local policy or update the policy with a bounded justification.", "SEMCONV.local-policy", "warning"),
    "ag.missing_signal": _entry("diagnosability", "Assign the layer owner and emit the signal required by the assume-guarantee obligation.", "AG.required-signal"),
    "ag.missing_field": _entry("diagnosability", "Attach the field required by the layer-local assume-guarantee obligation.", "AG.required-field"),
    "ag.predicate": _entry("diagnosability", "Emit a witness whose field value satisfies the layer-local predicate.", "AG.field-predicate"),
    "ag.alternative_missing": _entry("diagnosability", "Emit one of the layer-local alternative evidence paths.", "AG.alternative-disjunction"),
    "ag.scenario_unanswerable": _entry("diagnosability", "Provide the minimum observations needed by the assigned incident-response layer.", "AG.scenario-adequacy"),
    "ag.temporal_property": _entry("diagnosability", "Preserve the temporal property assigned to this layer.", "AG.temporal-property"),
    "ag.undocumented_transformation": _entry("preservation", "Document or remove collector/exporter transformations observed in the finite trace.", "AG.collector-assumption"),
    "refinement.malformed_contract": _entry("refinement", "Lint both contracts before comparing refinement.", "REF.well-formedness"),
    "refinement.service_mismatch": _entry("refinement", "Compare contracts for the same service or declare an organization/team refinement scope.", "REF.service-scope"),
    "refinement.required_signal_removed": _entry("refinement", "Keep every required base signal, scenario, temporal property, alternative obligation, and service guarantee required in the candidate.", "REF.requirement-preservation"),
    "refinement.required_field_removed": _entry("refinement", "Keep every required base field required in the candidate contract.", "REF.requirement-preservation"),
    "refinement.field_predicate_weakened": _entry("refinement", "Change the candidate predicate to be equal to or stronger than the inherited base predicate.", "REF.requirement-preservation"),
    "refinement.privacy_weakened": _entry("refinement", "Keep inherited privacy classifications, sensitivity, and allowed transformation sets at least as restrictive.", "REF.privacy-nonweakening", disclosure_sensitivity="responsible-disclosure"),
    "refinement.transformation_policy_weakened": _entry("refinement", "Do not approve new transformations or drop inherited preservation scenarios unless the base policy is changed first.", "REF.privacy-nonweakening"),
    "refinement.strict_policy_weakened": _entry("refinement", "Keep strict closed-world validation enabled and avoid adding new escape hatches in the candidate.", "REF.requirement-preservation"),
    "refinement.assumption_strengthened": _entry("refinement", "Do not add harder collector, environment, on-call, sampling, or retention assumptions in a refining contract.", "REF.assumption-compatibility"),
    "contract_diff.new_obligation": _entry("refinement", "Review the new telemetry obligation and ensure fixtures, owners, and rollout plans cover it.", "DIFF.obligation-added", "info"),
    "contract_diff.removed_obligation": _entry("refinement", "Confirm that removing the telemetry obligation is intentional and does not regress incident diagnosability.", "DIFF.obligation-removed", "warning"),
    "contract_diff.privacy_changed": _entry("privacy-security", "Review privacy-classification or transformation changes with the data owner before merging.", "DIFF.privacy-change", "warning", disclosure_sensitivity="responsible-disclosure"),
    "contract_diff.diagnosability_claim_changed": _entry("diagnosability", "Review changed incident-question, temporal, alternative, or preservation claims against real fixtures.", "DIFF.diagnosability-claim", "warning"),
    "static.missing_instrumentation": _entry("static-coverage", "Add source instrumentation with the expected stable telemetry name.", "STATIC.signal-literal"),
    "static.no_sources": _entry("static-coverage", "Pass source files or directories to the static checker.", "STATIC.source-domain"),
    "static.secret_logging": _entry("privacy-security", "Remove the sensitive value from logs or log only a redacted/hash surrogate.", "STATIC.raw-sensitive-log", disclosure_sensitivity="responsible-disclosure"),
    "static.missing_correlation": _entry("diagnosability", "Include a trace_id, request_id, or configured correlation field in error logs.", "STATIC.correlation-evidence"),
    "static.unbounded_label": _entry("operability", "Avoid user-controlled/high-cardinality metric labels or add bucketing.", "STATIC.cardinality-risk", "warning"),
    "scenario.not_found": _entry("scenario", "Add or select a scenario that matches the incident question.", "SCENARIO.selection"),
    "scenario.requirement_type": _entry("scenario", "Describe scenario requirements as objects.", "SCENARIO.requirement-wf"),
    "scenario.missing_signal": _entry("diagnosability", "Emit the signal needed to answer the scenario question.", "ADEQ.required-signal"),
    "scenario.missing_field": _entry("diagnosability", "Emit the field needed to answer the scenario question.", "ADEQ.required-field"),
    "scenario.alternative_missing": _entry("diagnosability", "Emit one alternative observation that can answer the scenario question.", "ADEQ.alternative-observation"),
    "preservation.contract_obligation": _entry("preservation", "Change or configure the transformation so transformed telemetry still satisfies obligations that held before transformation.", "PRES.runtime-obligation"),
    "preservation.scenario_signal": _entry("preservation", "Keep at least one transformed signal witness for each selected diagnosability requirement.", "PRES.adequacy-signal"),
    "preservation.scenario_field": _entry("preservation", "Keep the transformed field, or provide an approved surrogate that still answers the selected incident question.", "PRES.adequacy-field"),
    "otlp.dropped_evidence": _entry("input", "Inspect collector/exporter dropped-count fields before relying on complete contract evidence.", "OTLP.dropped-evidence", "warning"),
    "otlp.malformed_record": _entry("input", "Fix or exclude malformed OTLP JSONL records before asserting full export coverage.", "OTLP.malformed-record", "warning"),
    "otlp.skipped_record": _entry("input", "Fix malformed OTLP containers or unsupported item shapes so importer semantics are complete.", "OTLP.skipped-record", "warning"),
    "otlp.unsupported_metric": _entry("input", "Add importer support or avoid the unsupported metric encoding before making metric-contract claims.", "OTLP.unsupported-metric", "warning"),
    "otlp.unsupported_top_level": _entry("input", "Document unsupported top-level OTLP fields as validity threats or add bounded importer support.", "OTLP.unsupported-top-level", "info"),
    "otlp.normalized_alias": _entry("input", "Prefer canonical OTLP JSON field names, or keep alias normalization diagnostics with the import artifact.", "OTLP.alias-normalization", "info"),
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
