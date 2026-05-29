# Runtime monitor report: gitlab.com-database

- Model: `bounded-runtime-monitor-v1`
- Judgement: `compile(C) ⇓ M; M ⊢ e₁…eₙ ⇓ R`
- Pass: `false`
- Events: 4 input / 4 service-relevant
- Findings: 10
- Findings by code: `{"telemetry.allowed_values": 4, "telemetry.missing_field": 2, "telemetry.missing_signal": 1, "telemetry.numeric_max": 2, "telemetry.temporal_response": 1}`
- Compiled monitors: 5 signal, 0 sequence, 2 temporal-property
- Observed memory envelope: 2 active groups, 1 pending responses, 0 sequence-window events

## Semantics and memory bound

A contract compiles to deterministic per-clause monitors. Safety and absence clauses are checked per event; bounded response and temporal sequences retain only active sliding-window witnesses; ordering and deadline clauses retain prefix summaries per group; required signal clauses retain matched bits plus per-witness predicate findings.

O(|signal obligations| + |groups| × |prefix summaries| + active events inside declared windows + findings). The report includes observed active groups and pending-window witnesses for the concrete run.

## Findings

- **error `telemetry.numeric_max`** (SAT.numeric-upper-bound): field 'value' value 4294967296 is above maximum 104857600
- **error `telemetry.allowed_values`** (SAT.allowed-values): field 'target_role' value 'primary' is not allowed
- **error `telemetry.missing_field`** (SAT.required-field): log 'database.destructive_command' missing required field 'correlation_id'
- **error `telemetry.missing_field`** (SAT.required-field): log 'database.destructive_command' missing required field 'command_guard_result'
- **error `telemetry.allowed_values`** (SAT.allowed-values): field 'value' value False is not allowed
- **error `telemetry.allowed_values`** (SAT.allowed-values): field 'source' value 'lvm_snapshot' is not allowed
- **error `telemetry.numeric_max`** (SAT.numeric-upper-bound): field 'backup_age_hours' value 6 is above maximum 1
- **error `telemetry.allowed_values`** (SAT.allowed-values): field 'source_environment' value 'staging' is not allowed
- **error `telemetry.missing_signal`** (SAT.required-signal): required log 'backup.pg_dump.failed' was not emitted
- **error `telemetry.temporal_response`** (SAT.temporal-response): backup-failure-alert-within-response-window: no response 'backup.pg_dump.failed' within 1500ms after trigger 'backup.pg_dump.success'
