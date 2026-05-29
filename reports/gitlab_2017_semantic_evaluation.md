# Contract semantic evaluation: gitlab.com-database

- Model: `contract-small-step-semantics-v1`
- Judgement: `⟨T,C,σ⟩ ⇓ R`
- Pass: `false`
- Aligned with deterministic checker: `true`
- Events: 7 input / 6 service-relevant
- Small steps: 12
- Findings: 14
- Findings by code: `{'telemetry.allowed_values': 4, 'telemetry.missing_field': 3, 'telemetry.numeric_max': 2, 'telemetry.strict_undeclared_signal': 1, 'telemetry.strict_undocumented_transformation': 1, 'telemetry.strict_unexpected_field': 2, 'telemetry.strict_unmodeled_service': 1}`

## Relation

A finite trace T and contract C evaluate by deterministic small steps: well-formedness, service projection, signal obligations, correlation, temporal sequence and temporal-logic obligations, alternative disjunctions, and optional strict closed-world checks. The denotation R is the ordered multiset of checker finding signatures; alignment holds when the small-step denotation equals validate_events(C,T).

## Rules

- **WF** — Evaluate contract shape and schema obligations before telemetry obligations.
- **PROJECT** — Restrict runtime satisfaction to events for C.service or unscoped events.
- **SIGNAL** — For each required span/log/metric, find witnesses and check field predicates.
- **CORRELATION** — Check configured shared correlation keys across required signal kinds.
- **TEMPORAL** — Check finite ordered sequences within declared incident windows.
- **TEMPORAL-PROPERTY** — Check safety, absence, bounded-response, ordering, and deadline properties over finite traces.
- **ALTERNATIVE** — Evaluate required finite disjunctions over equivalent evidence paths.
- **STRICT** — Optionally strengthen satisfaction with closed-world checks.

## Small-step derivation

### 1. WF — contract well-formedness

- Status: `satisfied`
- Findings: 0
- Evidence: `{'contract_service': 'gitlab.com-database', 'input_events': 7}`

### 2. PROJECT — service projection

- Status: `satisfied`
- Findings: 0
- Evidence: `{'service': 'gitlab.com-database', 'retained_events': 6, 'ignored_events': 1, 'counts_by_kind': {'log': 3, 'metric': 2, 'span': 1}}`

### 3. SIGNAL — span disaster_recovery.restore_attempt

- Status: `violated`
- Findings: 3
- Obligation: `span disaster_recovery.restore_attempt` required=`true`
- Matching event lines: `[5]`
- Fields: backup_age_hours=present, source=present, source_environment=present
- Step findings:
  - `telemetry.allowed_values` field 'source' value 'lvm_snapshot' is not allowed
  - `telemetry.numeric_max` field 'backup_age_hours' value 6 is above maximum 1
  - `telemetry.allowed_values` field 'source_environment' value 'staging' is not allowed

### 4. SIGNAL — metric postgres.replication.lag_bytes

- Status: `violated`
- Findings: 1
- Obligation: `metric postgres.replication.lag_bytes` required=`true`
- Matching event lines: `[1]`
- Fields: incident_id=present, primary_host=present, replica_host=present, value=present
- Step findings:
  - `telemetry.numeric_max` field 'value' value 4294967296 is above maximum 104857600

### 5. SIGNAL — metric backup.pg_dump.success

- Status: `violated`
- Findings: 1
- Obligation: `metric backup.pg_dump.success` required=`true`
- Matching event lines: `[3]`
- Fields: backup_job_id=present, database_version=present, destination=present, tool_version=present, value=present
- Step findings:
  - `telemetry.allowed_values` field 'value' value False is not allowed

### 6. SIGNAL — log database.destructive_command

- Status: `violated`
- Findings: 3
- Obligation: `log database.destructive_command` required=`true`
- Matching event lines: `[2]`
- Fields: actor_role=present, command_guard_result=absent, correlation_id=absent, intended_host=present, target_host=present, target_role=present
- Step findings:
  - `telemetry.allowed_values` field 'target_role' value 'primary' is not allowed
  - `telemetry.missing_field` log 'database.destructive_command' missing required field 'correlation_id'
  - `telemetry.missing_field` log 'database.destructive_command' missing required field 'command_guard_result'

### 7. SIGNAL — log backup.pg_dump.failed

- Status: `violated`
- Findings: 1
- Obligation: `log backup.pg_dump.failed` required=`true`
- Matching event lines: `[4]`
- Fields: alert_delivered=absent, alert_route=present, backup_job_id=present, destination=present
- Step findings:
  - `telemetry.missing_field` log 'backup.pg_dump.failed' missing required field 'alert_delivered'

### 8. CORRELATION — correlation policy

- Status: `satisfied`
- Findings: 0
- Evidence: `{'declared': False}`

### 9. TEMPORAL — temporal sequences

- Status: `satisfied`
- Findings: 0
- Evidence: `{'sequence_count': 0, 'sequences': []}`

### 10. TEMPORAL-PROPERTY — temporal logic properties

- Status: `satisfied`
- Findings: 0
- Evidence: `{'property_count': 2, 'properties': [{'id': 'backup-failure-alert-within-response-window', 'type': 'bounded_response', 'group_by': ['backup_job_id'], 'within_ms': 1500}, {'id': 'replication-lag-before-destructive-command', 'type': 'ordering', 'group_by': [], 'within_ms': None}]}`

### 11. ALTERNATIVE — alternative obligations

- Status: `satisfied`
- Findings: 0
- Evidence: `{'summary': {'groups': 1, 'required_groups': 1, 'satisfied_groups': 1, 'unsatisfied_required_groups': 0, 'pass': True}, 'obligations': [{'id': 'destructive-command-location-evidence', 'required': True, 'satisfied': True, 'winning_option': 'structured-log'}]}`

### 12. STRICT — closed-world validation

- Status: `violated`
- Findings: 5
- Evidence: `{'enabled': True, 'events_checked': 7}`
- Step findings:
  - `telemetry.strict_unexpected_field` metric 'postgres.replication.lag_bytes' emitted undeclared field 'collector_pipeline'
  - `telemetry.strict_undocumented_transformation` collector transformation 'tail_sampling' is not documented by contract metadata
  - `telemetry.strict_unexpected_field` log 'backup.pg_dump.failed' emitted undeclared field 'notification_status'
  - `telemetry.strict_undeclared_signal` log 'database.replication.debug' is not declared by the contract
  - `telemetry.strict_unmodeled_service` event service 'collector-gateway' is not modeled by contract service 'gitlab.com-database'

## Denotation alignment

- Small-step finding signatures: 14
- Checker finding signatures: 14
- Mismatches: `{'missing_from_small_step': [], 'extra_in_small_step': []}`

## Findings

- **error `telemetry.allowed_values`** (SAT.allowed-values): field 'source' value 'lvm_snapshot' is not allowed
- **error `telemetry.numeric_max`** (SAT.numeric-upper-bound): field 'backup_age_hours' value 6 is above maximum 1
- **error `telemetry.allowed_values`** (SAT.allowed-values): field 'source_environment' value 'staging' is not allowed
- **error `telemetry.numeric_max`** (SAT.numeric-upper-bound): field 'value' value 4294967296 is above maximum 104857600
- **error `telemetry.allowed_values`** (SAT.allowed-values): field 'value' value False is not allowed
- **error `telemetry.allowed_values`** (SAT.allowed-values): field 'target_role' value 'primary' is not allowed
- **error `telemetry.missing_field`** (SAT.required-field): log 'database.destructive_command' missing required field 'correlation_id'
- **error `telemetry.missing_field`** (SAT.required-field): log 'database.destructive_command' missing required field 'command_guard_result'
- **error `telemetry.missing_field`** (SAT.required-field): log 'backup.pg_dump.failed' missing required field 'alert_delivered'
- **error `telemetry.strict_unexpected_field`** (STRICT.field-closed-world): metric 'postgres.replication.lag_bytes' emitted undeclared field 'collector_pipeline'
- **error `telemetry.strict_undocumented_transformation`** (STRICT.transformation-documented): collector transformation 'tail_sampling' is not documented by contract metadata
- **error `telemetry.strict_unexpected_field`** (STRICT.field-closed-world): log 'backup.pg_dump.failed' emitted undeclared field 'notification_status'
- **error `telemetry.strict_undeclared_signal`** (STRICT.signal-closed-world): log 'database.replication.debug' is not declared by the contract
- **error `telemetry.strict_unmodeled_service`** (STRICT.service-closed-world): event service 'collector-gateway' is not modeled by contract service 'gitlab.com-database'
