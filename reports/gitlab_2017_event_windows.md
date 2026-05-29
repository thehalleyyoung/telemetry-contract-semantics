# Event-window report

- Model: `event-window-grouping-v1`
- Service: `gitlab.com-database`
- Judgement: `T ⊨ C ⇓ F; group(T,F,K) ⇓ W`
- Pass: `False`
- Events: 4
- Findings: 10
- Windows: 5 (5 with findings)
- Dimensions: incident
- Incident slice: 2000 ms

## Findings by code

- `telemetry.allowed_values`: 4
- `telemetry.missing_field`: 2
- `telemetry.missing_signal`: 1
- `telemetry.numeric_max`: 2
- `telemetry.temporal_response`: 1

## Windows

### `global:contract=all`

- Dimension: `global`
- Event count: 0
- Finding count: 1
- Codes: `telemetry.missing_signal`=1
  - error `telemetry.missing_signal` at `events[log=backup.pg_dump.failed]`: required log 'backup.pg_dump.failed' was not emitted

### `incident:incident_id=gitlab-2017-db-outage`

- Dimension: `incident`
- Event count: 1
- Finding count: 1
- Services: gitlab.com-database
- Time range ms: 0.0..0.0
- Codes: `telemetry.numeric_max`=1
  - error `telemetry.numeric_max` at `event[1].value`: field 'value' value 4294967296 is above maximum 104857600

### `incident:slice_ms=0`

- Dimension: `incident`
- Event count: 2
- Finding count: 4
- Services: gitlab.com-database
- Time range ms: 0.0..1000.0
- Codes: `telemetry.allowed_values`=1, `telemetry.missing_field`=2, `telemetry.numeric_max`=1
  - error `telemetry.numeric_max` at `event[1].value`: field 'value' value 4294967296 is above maximum 104857600
  - error `telemetry.allowed_values` at `event[2].target_role`: field 'target_role' value 'primary' is not allowed
  - error `telemetry.missing_field` at `event[2].correlation_id`: log 'database.destructive_command' missing required field 'correlation_id'
  - error `telemetry.missing_field` at `event[2].command_guard_result`: log 'database.destructive_command' missing required field 'command_guard_result'

### `incident:slice_ms=2000`

- Dimension: `incident`
- Event count: 1
- Finding count: 2
- Services: gitlab.com-database
- Time range ms: 2000.0..2000.0
- Codes: `telemetry.allowed_values`=1, `telemetry.temporal_response`=1
  - error `telemetry.allowed_values` at `event[3].value`: field 'value' value False is not allowed
  - error `telemetry.temporal_response` at `event[3]`: backup-failure-alert-within-response-window: no response 'backup.pg_dump.failed' within 1500ms after trigger 'backup.pg_dump.success'

### `incident:slice_ms=4000`

- Dimension: `incident`
- Event count: 1
- Finding count: 3
- Services: gitlab.com-database
- Time range ms: 4000.0..4000.0
- Codes: `telemetry.allowed_values`=2, `telemetry.numeric_max`=1
  - error `telemetry.allowed_values` at `event[4].source`: field 'source' value 'lvm_snapshot' is not allowed
  - error `telemetry.numeric_max` at `event[4].backup_age_hours`: field 'backup_age_hours' value 6 is above maximum 1
  - error `telemetry.allowed_values` at `event[4].source_environment`: field 'source_environment' value 'staging' is not allowed

## Contract/global findings

- error `telemetry.missing_signal`: required log 'backup.pg_dump.failed' was not emitted
