# Finding taxonomy

- Schema version: `1.0`
- Rules: 121
- Categories: `{"contract": 27, "diagnosability": 32, "input": 7, "operability": 3, "preservation": 5, "privacy-security": 11, "refinement": 11, "scenario": 2, "schema": 19, "static-coverage": 4}`
- Default severities: `{"error": 91, "info": 3, "warning": 27}`
- SARIF levels: `{"error": 91, "note": 3, "warning": 27}`

## Rule catalog

| Code | Category | Severity | Formal clause | SARIF | CI fail-on | Disclosure | Owner | Remediation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ag.alternative_missing | diagnosability | error | AG.alternative-disjunction | error | error | internal | contract service owner | Emit one of the layer-local alternative evidence paths. |
| ag.missing_field | diagnosability | error | AG.required-field | error | error | internal | contract service owner | Attach the field required by the layer-local assume-guarantee obligation. |
| ag.missing_signal | diagnosability | error | AG.required-signal | error | error | internal | contract service owner | Assign the layer owner and emit the signal required by the assume-guarantee obligation. |
| ag.predicate | diagnosability | error | AG.field-predicate | error | error | internal | contract service owner | Emit a witness whose field value satisfies the layer-local predicate. |
| ag.scenario_unanswerable | diagnosability | error | AG.scenario-adequacy | error | error | internal | contract service owner | Provide the minimum observations needed by the assigned incident-response layer. |
| ag.temporal_property | diagnosability | error | AG.temporal-property | error | error | internal | contract service owner | Preserve the temporal property assigned to this layer. |
| ag.undocumented_transformation | preservation | error | AG.collector-assumption | error | error | internal | contract service owner | Document or remove collector/exporter transformations observed in the finite trace. |
| contract.allowed_values_type | contract | error | WF.allowed-values | error | error | internal | contract service owner | Declare allowed_values as an array. |
| contract.alternative_obligation | contract | error | WF.alternative-obligation | error | error | internal | contract service owner | Declare each alternative obligation with an id and a non-empty any_of list of signal options. |
| contract.assume_guarantee | contract | error | WF.assume-guarantee | error | error | internal | contract service owner | Declare assume-guarantee obligations under service_guarantees, collector_assumptions, environment_assumptions, or oncall_obligations with concrete finite-trace evidence. |
| contract.conditional_requirement | contract | error | WF.conditional | error | error | internal | contract service owner | Declare conditional requirements with an if field condition and then fields list. |
| contract.duplicate_field | contract | error | WF.unique-field | error | error | internal | contract service owner | Declare each field name in only one of fields, attributes, or tags for a signal. |
| contract.duplicate_signal | contract | error | WF.unique-signal | error | error | internal | contract service owner | Keep one contract definition per signal name and kind. |
| contract.field_definitions | contract | error | WF.field-definitions | error | error | internal | contract service owner | Declare reusable field definitions as an object of field specs. |
| contract.field_ref | contract | error | WF.field-reference | error | error | internal | contract service owner | Reference an existing field definition or inline the field spec. |
| contract.field_ref_cycle | contract | error | WF.field-reference-acyclic | error | error | internal | contract service owner | Remove cyclic field-definition references. |
| contract.field_type | contract | error | WF.field-type | error | error | internal | contract service owner | Use one of string, integer, number, boolean, object, array, or null. |
| contract.forbidden_patterns_type | contract | error | WF.forbidden-pattern | error | error | internal | contract service owner | Declare forbidden_patterns as a string, object, or array of strings/objects. |
| contract.hyperproperty | contract | error | WF.hyperproperty | error | error | internal | contract service owner | Declare hyperproperties with a valid type, witness fields, and pair/set quantification keys. |
| contract.invalid_regex | contract | error | WF.regex | error | error | internal | contract service owner | Fix the regular expression in the contract. |
| contract.numeric_bound_type | contract | error | WF.numeric-bound | error | error | internal | contract service owner | Declare min and max bounds as numbers. |
| contract.numeric_bounds | contract | error | WF.numeric-interval | error | error | internal | contract service owner | Ensure min is less than or equal to max. |
| contract.policy_stub | contract | error | WF.policy-stub | error | error | internal | contract service owner | Declare sampling and retention policy stubs with machine-readable rates, strategies, and day counts. |
| contract.privacy_policy | privacy-security | error | WF.privacy-policy | error | error | responsible-disclosure | contract service owner | Declare a known privacy classification and an allowed transformation such as redacted, hashed, tokenized, bucketed, or omitted. |
| contract.required_type | contract | error | WF.required-boolean | error | error | internal | contract service owner | Use a boolean for required flags. |
| contract.schema | contract | error | WF.schema | error | error | internal | contract service owner | Update the contract so it conforms to docs/contract.schema.json. |
| contract.section_type | contract | error | WF.signal-section | error | error | internal | contract service owner | Use arrays for spans, metrics, and logs sections. |
| contract.sensitive_field_unclassified | schema | warning | WF.privacy-classification | warning | warning | internal | contract service owner | Classify sensitive fields with sensitivity and forbid raw-secret patterns. |
| contract.service | contract | error | WF.service | error | error | internal | contract service owner | Add a non-empty service name. |
| contract.severity_policy | contract | error | WF.severity-policy | error | error | internal | contract service owner | Use a known log severity threshold such as WARN, ERROR, or FATAL. |
| contract.signal_name | contract | error | WF.signal-name | error | error | internal | contract service owner | Give each signal a stable telemetry name. |
| contract.signal_type | contract | error | WF.signal-object | error | error | internal | contract service owner | Describe each signal as an object. |
| contract.strict_policy | contract | error | WF.strict-policy | error | error | internal | contract service owner | Declare strict-validation escape hatches as bounded service, signal, field, or transformation lists. |
| contract.temporal_property | contract | error | WF.temporal-property | error | error | internal | contract service owner | Declare temporal properties with a valid type, selectors, predicates, grouping keys, and positive time bounds. |
| contract.temporal_sequence | contract | error | WF.temporal-sequence | error | error | internal | contract service owner | Declare temporal sequences with valid steps, kinds, group_by keys, and positive windows. |
| contract.unit | schema | error | WF.unit | error | error | internal | contract service owner | Use a supported unit such as ms, bytes, percent, count, timestamp_ms, or usd. |
| contract.version | contract | error | WF.version | error | error | internal | contract service owner | Declare contract version 1.0. |
| contract_diff.diagnosability_claim_changed | diagnosability | warning | DIFF.diagnosability-claim | warning | warning | internal | contract service owner | Review changed incident-question, temporal, alternative, or preservation claims against real fixtures. |
| contract_diff.new_obligation | refinement | info | DIFF.obligation-added | note | info | internal | contract service owner | Review the new telemetry obligation and ensure fixtures, owners, and rollout plans cover it. |
| contract_diff.privacy_changed | privacy-security | warning | DIFF.privacy-change | warning | warning | responsible-disclosure | contract service owner | Review privacy-classification or transformation changes with the data owner before merging. |
| contract_diff.removed_obligation | refinement | warning | DIFF.obligation-removed | warning | warning | internal | contract service owner | Confirm that removing the telemetry obligation is intentional and does not regress incident diagnosability. |
| input.load_error | input | error | INPUT.parse | error | error | internal | contract service owner | Fix the referenced input path or file format. |
| otlp.dropped_evidence | input | warning | OTLP.dropped-evidence | warning | warning | internal | contract service owner | Inspect collector/exporter dropped-count fields before relying on complete contract evidence. |
| otlp.malformed_record | input | warning | OTLP.malformed-record | warning | warning | internal | contract service owner | Fix or exclude malformed OTLP JSONL records before asserting full export coverage. |
| otlp.normalized_alias | input | info | OTLP.alias-normalization | note | info | internal | contract service owner | Prefer canonical OTLP JSON field names, or keep alias normalization diagnostics with the import artifact. |
| otlp.skipped_record | input | warning | OTLP.skipped-record | warning | warning | internal | contract service owner | Fix malformed OTLP containers or unsupported item shapes so importer semantics are complete. |
| otlp.unsupported_metric | input | warning | OTLP.unsupported-metric | warning | warning | internal | contract service owner | Add importer support or avoid the unsupported metric encoding before making metric-contract claims. |
| otlp.unsupported_top_level | input | info | OTLP.unsupported-top-level | note | info | internal | contract service owner | Document unsupported top-level OTLP fields as validity threats or add bounded importer support. |
| preservation.contract_obligation | preservation | error | PRES.runtime-obligation | error | error | internal | contract service owner | Change or configure the transformation so transformed telemetry still satisfies obligations that held before transformation. |
| preservation.scenario_field | preservation | error | PRES.adequacy-field | error | error | internal | contract service owner | Keep the transformed field, or provide an approved surrogate that still answers the selected incident question. |
| preservation.scenario_signal | preservation | error | PRES.adequacy-signal | error | error | internal | contract service owner | Keep at least one transformed signal witness for each selected diagnosability requirement. |
| refinement.assumption_strengthened | refinement | error | REF.assumption-compatibility | error | error | internal | contract service owner | Do not add harder collector, environment, on-call, sampling, or retention assumptions in a refining contract. |
| refinement.field_predicate_weakened | refinement | error | REF.requirement-preservation | error | error | internal | contract service owner | Change the candidate predicate to be equal to or stronger than the inherited base predicate. |
| refinement.malformed_contract | refinement | error | REF.well-formedness | error | error | internal | contract service owner | Lint both contracts before comparing refinement. |
| refinement.privacy_weakened | refinement | error | REF.privacy-nonweakening | error | error | responsible-disclosure | contract service owner | Keep inherited privacy classifications, sensitivity, and allowed transformation sets at least as restrictive. |
| refinement.required_field_removed | refinement | error | REF.requirement-preservation | error | error | internal | contract service owner | Keep every required base field required in the candidate contract. |
| refinement.required_signal_removed | refinement | error | REF.requirement-preservation | error | error | internal | contract service owner | Keep every required base signal, scenario, temporal property, alternative obligation, and service guarantee required in the candidate. |
| refinement.service_mismatch | refinement | error | REF.service-scope | error | error | internal | contract service owner | Compare contracts for the same service or declare an organization/team refinement scope. |
| refinement.strict_policy_weakened | refinement | error | REF.requirement-preservation | error | error | internal | contract service owner | Keep strict closed-world validation enabled and avoid adding new escape hatches in the candidate. |
| refinement.transformation_policy_weakened | refinement | error | REF.privacy-nonweakening | error | error | internal | contract service owner | Do not approve new transformations or drop inherited preservation scenarios unless the base policy is changed first. |
| scenario.alternative_missing | diagnosability | error | ADEQ.alternative-observation | error | error | internal | contract service owner | Emit one alternative observation that can answer the scenario question. |
| scenario.missing_field | diagnosability | error | ADEQ.required-field | error | error | internal | contract service owner | Emit the field needed to answer the scenario question. |
| scenario.missing_signal | diagnosability | error | ADEQ.required-signal | error | error | internal | contract service owner | Emit the signal needed to answer the scenario question. |
| scenario.not_found | scenario | error | SCENARIO.selection | error | error | internal | contract service owner | Add or select a scenario that matches the incident question. |
| scenario.requirement_type | scenario | error | SCENARIO.requirement-wf | error | error | internal | contract service owner | Describe scenario requirements as objects. |
| semconv.legacy_attribute | schema | warning | SEMCONV.attribute-alias | warning | warning | internal | contract service owner | Rename the legacy attribute to the cited current OpenTelemetry semantic-convention attribute. |
| semconv.local_policy | schema | warning | SEMCONV.local-policy | warning | warning | internal | contract service owner | Satisfy the contract's metadata.semantic_conventions local policy or update the policy with a bounded justification. |
| semconv.metric_unit | schema | warning | SEMCONV.metric-unit | warning | warning | internal | contract service owner | Declare the metric unit explicitly and consider removing the unit-only suffix from the metric name. |
| semconv.missing_attribute | schema | warning | SEMCONV.required-attribute | warning | warning | internal | contract service owner | Add the cited OpenTelemetry semantic-convention attribute to the contract and emitted telemetry, or document an artifact-scoped local exception. |
| semconv.signal_name | schema | warning | SEMCONV.signal-name | warning | warning | internal | contract service owner | Rename the signal to the cited low-cardinality OpenTelemetry semantic-convention shape. |
| static.inconsistent_retryability | diagnosability | warning | STATIC.retryability-evidence | warning | warning | internal | contract service owner | Attach a bounded retryable value when the contract requires retry guidance. |
| static.metric_description | diagnosability | warning | STATIC.metric-description | warning | warning | internal | contract service owner | Declare the metric description in the OpenTelemetry metric API call. |
| static.metric_unit | schema | warning | STATIC.metric-unit | warning | warning | internal | contract service owner | Declare the metric unit in the OpenTelemetry metric API call. |
| static.missing_correlation | diagnosability | error | STATIC.correlation-evidence | error | error | internal | contract service owner | Include a trace_id, request_id, or configured correlation field in error logs. |
| static.missing_error_status | diagnosability | warning | STATIC.error-status | warning | warning | internal | contract service owner | Set the OpenTelemetry span status to ERROR on error paths. |
| static.missing_exception_recording | diagnosability | warning | STATIC.exception-recording | warning | warning | internal | contract service owner | Record caught exceptions on error spans so incident responders can inspect failure type and stack context. |
| static.missing_instrumentation | static-coverage | error | STATIC.signal-literal | error | error | internal | contract service owner | Add source instrumentation with the expected stable telemetry name. |
| static.missing_meter_name | static-coverage | warning | STATIC.meter-name | warning | warning | internal | contract service owner | Initialize the OpenTelemetry meter with the expected instrumentation scope name. |
| static.missing_remediation_field | diagnosability | warning | STATIC.remediation-evidence | warning | warning | internal | contract service owner | Attach a bounded remediation hint on error spans or logs when the contract requires operator guidance. |
| static.missing_semconv_attribute | schema | warning | STATIC.semconv-attribute | warning | warning | internal | contract service owner | Attach the required semantic-convention attribute in source instrumentation. |
| static.missing_tracer_name | static-coverage | warning | STATIC.tracer-name | warning | warning | internal | contract service owner | Initialize the OpenTelemetry tracer with the expected instrumentation scope name. |
| static.no_sources | static-coverage | error | STATIC.source-domain | error | error | internal | contract service owner | Pass source files or directories to the static checker. |
| static.pii_logging | privacy-security | error | STATIC.pii-sensitive-log | error | error | responsible-disclosure | contract service owner | Remove PII or tenant/customer identifiers from logs, or emit redacted/hash/bucketed surrogates. |
| static.secret_logging | privacy-security | error | STATIC.raw-sensitive-log | error | error | responsible-disclosure | contract service owner | Remove the sensitive value from logs or log only a redacted/hash surrogate. |
| static.unbounded_label | operability | warning | STATIC.cardinality-risk | warning | warning | internal | contract service owner | Avoid user-controlled/high-cardinality metric labels or add bucketing. |
| static.unsafe_payload_preview | privacy-security | warning | STATIC.payload-preview | warning | warning | responsible-disclosure | contract service owner | Replace raw payload/body previews with allowlisted sanitized previews or omit them. |
| telemetry.allowed_values | schema | error | SAT.allowed-values | error | error | internal | contract service owner | Normalize the field to one of the declared allowed values. |
| telemetry.alternative_missing | diagnosability | error | SAT.alternative-disjunction | error | error | internal | contract service owner | Emit at least one of the declared alternative evidence options with its required fields. |
| telemetry.cardinality | operability | warning | SAT.cardinality-bound | warning | warning | internal | contract service owner | Bucket, hash, drop, or bound labels with excessive cardinality. |
| telemetry.cardinality_policy | operability | warning | SAT.cardinality-policy | warning | warning | internal | contract service owner | Declare a max cardinality or explicitly allow unbounded values. |
| telemetry.conditional_missing_field | diagnosability | error | SAT.conditional-obligation | error | error | internal | contract service owner | When the triggering field is present, emit all fields required by the conditional requirement. |
| telemetry.correlation_mismatch | diagnosability | error | SAT.correlation-intersection | error | error | internal | contract service owner | Propagate at least one shared correlation key value across the required signal kinds. |
| telemetry.correlation_missing | diagnosability | error | SAT.correlation-presence | error | error | internal | contract service owner | Emit a trace_id, span_id, request_id, or configured correlation key on correlated signals. |
| telemetry.field_type | schema | error | SAT.field-type | error | error | internal | contract service owner | Emit the field using the contract's declared primitive type. |
| telemetry.forbidden_pattern | privacy-security | error | SAT.forbidden-pattern | error | error | responsible-disclosure | contract service owner | Redact, hash, or omit values matching forbidden sensitive patterns. |
| telemetry.hyper_pii_disclosure | privacy-security | error | HYP.pii-non-disclosure | error | error | responsible-disclosure | contract service owner | Redact, hash, tokenize, bucket, or omit sensitive values before they reach public telemetry sinks. |
| telemetry.hyper_tenant_interference | privacy-security | error | HYP.tenant-non-interference | error | error | responsible-disclosure | contract service owner | Do not allow telemetry for different tenants to share an isolation key such as trace_id, request_id, or session_id. |
| telemetry.log_message | diagnosability | error | SAT.log-message | error | error | internal | contract service owner | Use a stable log message or event name matching the contract. |
| telemetry.log_severity | diagnosability | error | SAT.log-severity | error | error | internal | contract service owner | Emit the log at the severity required for alerting and search. |
| telemetry.log_severity_min | diagnosability | error | SAT.log-severity-threshold | error | error | internal | contract service owner | Raise the emitted log severity to meet the contract's minimum severity policy. |
| telemetry.missing_field | diagnosability | error | SAT.required-field | error | error | internal | contract service owner | Attach the required attribute/tag/field to the signal. |
| telemetry.missing_signal | diagnosability | error | SAT.required-signal | error | error | internal | contract service owner | Emit the required span, metric, or log on the exercised path. |
| telemetry.numeric_max | schema | error | SAT.numeric-upper-bound | error | error | internal | contract service owner | Investigate or clamp values above the declared maximum. |
| telemetry.numeric_min | schema | error | SAT.numeric-lower-bound | error | error | internal | contract service owner | Investigate or clamp values below the declared minimum. |
| telemetry.pattern | schema | error | SAT.regex | error | error | internal | contract service owner | Normalize the field so it matches the declared pattern. |
| telemetry.pattern_type | schema | error | SAT.regex-domain | error | error | internal | contract service owner | Emit a string value when a regex pattern is required. |
| telemetry.privacy_transformation | privacy-security | error | SAT.privacy-preservation | error | error | responsible-disclosure | contract service owner | Emit the field using the transformation required by the contract privacy policy. |
| telemetry.sensitive_unclassified | privacy-security | warning | SAT.sensitive-classification | warning | warning | responsible-disclosure | contract service owner | Classify the field sensitivity and redact or hash the emitted value. |
| telemetry.sensitive_value | privacy-security | error | SAT.raw-sensitive-value | error | error | responsible-disclosure | contract service owner | Do not emit raw PII, credentials, or bearer tokens in telemetry. |
| telemetry.strict_undeclared_signal | schema | error | STRICT.signal-closed-world | error | error | internal | contract service owner | Declare the emitted signal in spans, metrics, logs, scenarios, or alternative obligations, or add an explicit strict allow_undeclared_signals escape hatch. |
| telemetry.strict_undocumented_transformation | preservation | error | STRICT.transformation-documented | error | error | internal | contract service owner | Document the collector transformation under metadata.transformation_preservation.approved_transformations or strict allow_collector_transformations. |
| telemetry.strict_unexpected_field | schema | error | STRICT.field-closed-world | error | error | internal | contract service owner | Declare the emitted field on the signal contract or add an explicit strict allowed_extra_fields escape hatch. |
| telemetry.strict_unmodeled_service | schema | error | STRICT.service-closed-world | error | error | internal | contract service owner | Either emit telemetry for the modeled service or add a bounded allow_unmodeled_services escape hatch. |
| telemetry.temporal_absence | diagnosability | error | SAT.temporal-absence | error | error | internal | contract service owner | Do not emit the forbidden event in traces covered by this absence property. |
| telemetry.temporal_deadline | diagnosability | error | SAT.temporal-deadline | error | error | internal | contract service owner | Emit the deadline-bound event before the declared time budget expires. |
| telemetry.temporal_missing_step | diagnosability | error | SAT.temporal-presence | error | error | internal | contract service owner | Emit every event required by the temporal sequence in the grouped incident window. |
| telemetry.temporal_order | diagnosability | error | SAT.temporal-order | error | error | internal | contract service owner | Emit telemetry in the order required by the temporal property or sequence. |
| telemetry.temporal_response | diagnosability | error | SAT.temporal-response | error | error | internal | contract service owner | Emit the required response event inside the bounded response window after each trigger. |
| telemetry.temporal_safety | diagnosability | error | SAT.temporal-safety | error | error | internal | contract service owner | Keep every matched event inside the declared temporal invariant. |
| telemetry.temporal_window | diagnosability | error | SAT.temporal-window | error | error | internal | contract service owner | Emit the temporal sequence within the declared bounded window. |
| telemetry.unit | schema | error | SAT.unit | error | error | internal | contract service owner | Emit a value that satisfies the field's declared unit constraints. |

