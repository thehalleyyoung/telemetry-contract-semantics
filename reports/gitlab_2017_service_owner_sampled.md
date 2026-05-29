# Service-owner telemetry report: gitlab.com-database

- Owner: `unknown`
- Pass: `false`
- Incident-readiness score: `76`
- Events: 4
- Sources: 0
- Findings: 20
- Findings by code: `{"scenario.missing_field": 2, "scenario.missing_signal": 1, "semconv.local_policy": 2, "semconv.metric_unit": 1, "semconv.missing_attribute": 4, "telemetry.allowed_values": 4, "telemetry.missing_field": 2, "telemetry.missing_signal": 1, "telemetry.numeric_max": 2, "telemetry.temporal_response": 1}`

## Contract coverage

| Kind | Required | Observed | Missing |
| --- | ---: | ---: | --- |
| span | 1 | 1 | none |
| metric | 2 | 2 | none |
| log | 2 | 1 | backup.pg_dump.failed |

## Failing obligations

- `telemetry.allowed_values` (error) at `event[4].source`: field 'source' value 'lvm_snapshot' is not allowed
- `telemetry.numeric_max` (error) at `event[4].backup_age_hours`: field 'backup_age_hours' value 6 is above maximum 1
- `telemetry.allowed_values` (error) at `event[4].source_environment`: field 'source_environment' value 'staging' is not allowed
- `telemetry.numeric_max` (error) at `event[1].value`: field 'value' value 4294967296 is above maximum 104857600
- `telemetry.allowed_values` (error) at `event[3].value`: field 'value' value False is not allowed
- `telemetry.allowed_values` (error) at `event[2].target_role`: field 'target_role' value 'primary' is not allowed
- `telemetry.missing_field` (error) at `event[2].correlation_id`: log 'database.destructive_command' missing required field 'correlation_id'
- `telemetry.missing_field` (error) at `event[2].command_guard_result`: log 'database.destructive_command' missing required field 'command_guard_result'
- `telemetry.missing_signal` (error) at `events[log=backup.pg_dump.failed]`: required log 'backup.pg_dump.failed' was not emitted
- `telemetry.temporal_response` (error) at `event[3]`: backup-failure-alert-within-response-window: no response 'backup.pg_dump.failed' within 1500ms after trigger 'backup.pg_dump.success'
- `semconv.missing_attribute` (warning) at `$.metrics[0].fields.db.system.name`: metric 'postgres.replication.lag_bytes' should declare semantic attribute 'db.system.name'
- `semconv.metric_unit` (warning) at `$.metrics[0].value.unit`: metric 'postgres.replication.lag_bytes' encodes unit suffix '_bytes' without declaring value.unit
- `semconv.missing_attribute` (warning) at `$.logs[0].fields.db.system.name`: log 'database.destructive_command' should declare semantic attribute 'db.system.name'
- `semconv.local_policy` (warning) at `$.metadata.semantic_conventions.required_attributes[0].attribute`: metric 'postgres.replication.lag_bytes' must declare local semantic attribute 'db.system.name'
- `semconv.missing_attribute` (warning) at `event[1].db.system.name`: metric 'postgres.replication.lag_bytes' should emit semantic attribute 'db.system.name'
- `semconv.missing_attribute` (warning) at `event[2].db.system.name`: log 'database.destructive_command' should emit semantic attribute 'db.system.name'
- `semconv.local_policy` (warning) at `event[1].db.system.name`: metric 'postgres.replication.lag_bytes' missing local semantic attribute 'db.system.name'
- `scenario.missing_field` (error) at `events[log=database.destructive_command].correlation_id`: scenario 'restore-readiness' cannot answer question without field 'correlation_id' on log 'database.destructive_command'
- `scenario.missing_field` (error) at `events[log=database.destructive_command].command_guard_result`: scenario 'restore-readiness' cannot answer question without field 'command_guard_result' on log 'database.destructive_command'
- `scenario.missing_signal` (error) at `events[log=backup.pg_dump.failed]`: scenario 'restore-readiness' requires log 'backup.pg_dump.failed'

## Privacy risks

No privacy/security findings in the supplied artifacts.

## Remediation priority

| Severity | Category | Owner | Count | Remediation |
| --- | --- | --- | ---: | --- |
| error | schema | contract service owner | 4 | Normalize the field to one of the declared allowed values. |
| error | diagnosability | contract service owner | 2 | Attach the required attribute/tag/field to the signal. |
| error | diagnosability | contract service owner | 2 | Emit the field needed to answer the scenario question. |
| error | schema | contract service owner | 2 | Investigate or clamp values above the declared maximum. |
| error | diagnosability | contract service owner | 1 | Emit the required span, metric, or log on the exercised path. |
| error | diagnosability | contract service owner | 1 | Emit the required response event inside the bounded response window after each trigger. |
| error | diagnosability | contract service owner | 1 | Emit the signal needed to answer the scenario question. |
| warning | schema | contract service owner | 4 | Add the cited OpenTelemetry semantic-convention attribute to the contract and emitted telemetry, or document an artifact-scoped local exception. |
| warning | schema | contract service owner | 2 | Satisfy the contract's metadata.semantic_conventions local policy or update the policy with a bounded justification. |
| warning | schema | contract service owner | 1 | Declare the metric unit explicitly and consider removing the unit-only suffix from the metric name. |

## Limitations

- Report summarizes supplied finite artifacts only; absence of findings is not a production guarantee.
- Static source links are limited to checked files and lightweight source extraction.

