# Transformation-preservation report: gitlab.com-database

- Model: `transformation-preservation-v1`
- Preserves selected obligations: `false`
- Approved transformations: `sampling`
- Source events: 5
- Transformed events: 4
- Events removed: 1
- Scenarios checked: 1
- Preservation findings: 5
- Findings by code: `{"preservation.contract_obligation": 1, "preservation.scenario_field": 3, "preservation.scenario_signal": 1}`

## Relation

For a contract C, source trace T, transformed trace T′, and approved transformations Δ, T′ preserves C when every runtime contract obligation and diagnosability witness that is satisfied in T remains satisfied in T′. The check is obligation-local: it reports newly destroyed evidence even when T already violates unrelated obligations.

## Preservation findings

- **error `preservation.contract_obligation`** at `events[log=backup.pg_dump.failed]`: transformation introduced telemetry.missing_signal: required log 'backup.pg_dump.failed' was not emitted
  - Details: `{"introduced_finding": {"category": "diagnosability", "ci": {"baseline_key_fields": ["code", "path", "contract_path", "event_index"], "default_fail_on": "error", "sarif_level": "error"}, "code": "telemetry.missing_signal", "contract_path": "$.logs[1]", "disclosure_sensitivity": "internal", "formal_clause": "SAT.required-signal", "message": "required log 'backup.pg_dump.failed' was not emitted", "path": "events[log=backup.pg_dump.failed]", "remediation": "Emit the required span, metric, or log on the exercised path.", "sarif_level": "error", "service_owner": "contract service owner", "severity": "error"}}`
- **error `preservation.scenario_signal`** at `events[log=backup.pg_dump.failed]`: transformation removed diagnosability witness $signal for log:backup.pg_dump.failed in scenario 'restore-readiness'
  - Details: `{"scenario": "restore-readiness", "source": "present", "transformed": "missing"}`
- **error `preservation.scenario_field`** at `events[log=backup.pg_dump.failed].alert_route`: transformation removed diagnosability witness alert_route for log:backup.pg_dump.failed in scenario 'restore-readiness'
  - Details: `{"scenario": "restore-readiness", "source": "present", "transformed": "missing"}`
- **error `preservation.scenario_field`** at `events[log=backup.pg_dump.failed].backup_job_id`: transformation removed diagnosability witness backup_job_id for log:backup.pg_dump.failed in scenario 'restore-readiness'
  - Details: `{"scenario": "restore-readiness", "source": "present", "transformed": "missing"}`
- **error `preservation.scenario_field`** at `events[log=backup.pg_dump.failed].destination`: transformation removed diagnosability witness destination for log:backup.pg_dump.failed in scenario 'restore-readiness'
  - Details: `{"scenario": "restore-readiness", "source": "present", "transformed": "missing"}`

## Scenario preservation

### `restore-readiness`

- Source answerable: `false`
- Transformed answerable: `false`
- Lost witnesses: 4
  - `log:backup.pg_dump.failed` lost `$signal` (present → missing)
  - `log:backup.pg_dump.failed` lost `alert_route` (present → missing)
  - `log:backup.pg_dump.failed` lost `backup_job_id` (present → missing)
  - `log:backup.pg_dump.failed` lost `destination` (present → missing)

## Limitations

- The relation is scoped to this contract's declared signals, field predicates, privacy transformations, and selected scenarios.
- The checker compares finite artifacts; it does not prove a collector implementation correct for all possible production traces.
- Historical case-study fixtures are reconstructed when their metadata says so; preservation claims are bounded to checked-in artifacts.

