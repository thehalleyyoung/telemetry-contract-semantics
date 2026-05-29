# Assume-guarantee report: gitlab.com-database

- Model: `assume-guarantee-telemetry-contracts-v1`
- Judgement: `A,T ⊢ layer obligation ⇓ satisfied | violated`
- Pass: `false`
- Obligations: 8
- Satisfied: 3
- Violated: 5
- Findings by code: `{"ag.missing_field": 6, "ag.missing_signal": 1, "ag.predicate": 2, "ag.scenario_unanswerable": 1, "ag.temporal_property": 1}`

## Relation

An assume-guarantee telemetry contract partitions finite-trace obligations by accountable layer: service emission guarantees, collector/exporter assumptions, environment assumptions, and on-call diagnostic obligations. A layer obligation is satisfied when its declared signal, scenario, temporal, alternative, or collector-transformation evidence is witnessed in the supplied finite trace; otherwise the report emits a layer-specific counterexample with event indices and missing fields.

## Layer summary

| Layer | Satisfied | Violated | Not applicable |
| --- | ---: | ---: | ---: |
| service | 0 | 2 | 0 |
| collector | 1 | 1 | 0 |
| environment | 2 | 0 | 0 |
| oncall | 0 | 2 | 0 |

## Obligations

- **destructive-command-guard-evidence** `violated` — service emission guarantee
  - Description: Database service/runbook instrumentation should emit enough structured evidence to distinguish intended host, actual target role, correlation id, and guard result.
  - Evidence: `{"fields": ["target_host", "intended_host", "target_role", "correlation_id", "command_guard_result"], "matching_event_indices": [2], "missing_fields": ["correlation_id", "command_guard_result"], "name": "database.destructive_command", "o...`
  - Findings:
    - `ag.missing_field` service emission guarantee 'destructive-command-guard-evidence' requires field 'correlation_id' on log 'database.destructive_command'
    - `ag.missing_field` service emission guarantee 'destructive-command-guard-evidence' requires field 'command_guard_result' on log 'database.destructive_command'
- **restorable-production-backup-guarantee** `violated` — service emission guarantee
  - Description: Recovery telemetry should guarantee that the selected restore source is verified, fresh, and from production backup evidence.
  - Evidence: `{"fields": ["source", "backup_age_hours", "source_environment"], "matching_event_indices": [4], "missing_fields": [], "name": "disaster_recovery.restore_attempt", "observed_fields": ["backup_age_hours", "source", "source_environment"], "...`
  - Findings:
    - `ag.predicate` service emission guarantee 'restorable-production-backup-guarantee' predicate on field 'source' was not witnessed
- **documented-transformations-only** `satisfied` — collector/exporter assumption
  - Description: Collector/exporter output may be sampled only by transformations declared in metadata.transformation_preservation.
  - Evidence: `{"approved_transformations": ["sampling"], "observed_transformations": {}, "undocumented_transformations": {}}`
- **backup-alert-preserved-in-export** `violated` — collector/exporter assumption
  - Description: Collector/exporter sampling must preserve the bounded backup-failure alert response needed for restore-readiness evidence.
  - Evidence: `{"temporal_property": "backup-failure-alert-within-response-window", "violations": [{"category": "diagnosability", "ci": {"baseline_key_fields": ["code", "path", "contract_path", "event_index"], "default_fail_on": "error", "sarif_level":...`
  - Findings:
    - `ag.temporal_property` collector/exporter assumption 'backup-alert-preserved-in-export' requires temporal property 'backup-failure-alert-within-response-window' to hold
- **backup-version-and-destination-evidence** `satisfied` — environment assumption
  - Description: The backup environment should expose destination and database/tool version evidence for selecting a restorable backup.
  - Evidence: `{"fields": ["backup_job_id", "destination", "database_version", "tool_version"], "matching_event_indices": [3], "missing_fields": [], "name": "backup.pg_dump.success", "observed_fields": ["backup_job_id", "database_version", "destination...`
- **replication-lag-context-evidence** `satisfied` — environment assumption
  - Description: The database environment should expose primary/replica lag context for stale-replica incident slices.
  - Evidence: `{"fields": ["primary_host", "replica_host", "incident_id"], "matching_event_indices": [1], "missing_fields": [], "name": "postgres.replication.lag_bytes", "observed_fields": ["incident_id", "primary_host", "replica_host"], "predicate_wit...`
- **backup-alert-delivered-to-responders** `violated` — on-call diagnostic obligation
  - Description: On-call diagnostic workflow should expose whether the backup failure alert was delivered to responders.
  - Evidence: `{"fields": ["backup_job_id", "destination", "alert_route", "alert_delivered"], "matching_event_indices": [], "missing_fields": ["backup_job_id", "destination", "alert_route", "alert_delivered"], "name": "backup.pg_dump.failed", "observed...`
  - Findings:
    - `ag.missing_signal` on-call diagnostic obligation 'backup-alert-delivered-to-responders' requires log 'backup.pg_dump.failed'
    - `ag.missing_field` on-call diagnostic obligation 'backup-alert-delivered-to-responders' requires field 'backup_job_id' on log 'backup.pg_dump.failed'
    - `ag.missing_field` on-call diagnostic obligation 'backup-alert-delivered-to-responders' requires field 'destination' on log 'backup.pg_dump.failed'
    - `ag.missing_field` on-call diagnostic obligation 'backup-alert-delivered-to-responders' requires field 'alert_route' on log 'backup.pg_dump.failed'
    - `ag.missing_field` on-call diagnostic obligation 'backup-alert-delivered-to-responders' requires field 'alert_delivered' on log 'backup.pg_dump.failed'
    - `ag.predicate` on-call diagnostic obligation 'backup-alert-delivered-to-responders' predicate on field 'alert_delivered' was not witnessed
- **restore-readiness-question-answerable** `violated` — on-call diagnostic obligation
  - Description: On-call incident evidence should answer the restore-readiness question declared by the contract.
  - Evidence: `{"answerable": false, "missing_evidence": [{"category": "diagnosability", "ci": {"baseline_key_fields": ["code", "path", "contract_path", "event_index"], "default_fail_on": "error", "sarif_level": "error"}, "code": "scenario.missing_fiel...`
  - Findings:
    - `ag.scenario_unanswerable` on-call diagnostic obligation 'restore-readiness-question-answerable' requires scenario 'restore-readiness' to be answerable

## Limitations

- The report checks finite supplied artifacts; it does not prove obligations over all production executions.
- Collector-preservation assumptions that require before/after traces should be paired with the preservation command for transformation-local proof evidence.
