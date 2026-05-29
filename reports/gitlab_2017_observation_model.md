# Telemetry Contracts Observation Model

Satisfaction: `T ⊨ C` — A finite telemetry trace T satisfies contract C when every well-formed contract obligation evaluates to true over the observations relevant to C.service under declared assumptions.

## Observation domain

| Object | Meaning | JSONL fields | OTLP fields | Checker use |
| --- | --- | --- | --- | --- |
| span | An operation interval in a finite trace event structure. | `kind=span`, `service`, `name`, `trace_id`, `span_id`, `parent_span_id`, `attributes`, `timestamp_ms`, `start_time_unix_nano`, `end_time_unix_nano` | `resourceSpans[].resource.attributes`, `scopeSpans[].spans[].name`, `traceId`, `spanId`, `parentSpanId`, `attributes`, `startTimeUnixNano`, `endTimeUnixNano`, `status`, `events`, `links` | presence, field predicates, correlation keys, temporal ordering, and scenario evidence |
| log | A timestamped diagnostic record that may attach to a trace/span. | `kind=log`, `service`, `name`, `severity`, `message`, `trace_id`, `span_id`, `fields`, `timestamp_ms`, `time_unix_nano` | `resourceLogs[].resource.attributes`, `scopeLogs[].logRecords[].body`, `severityText`, `traceId`, `spanId`, `attributes`, `timeUnixNano`, `observedTimeUnixNano` | severity/message policies, field predicates, privacy checks, correlation, and incident-question evidence |
| metric | A measurement point or aggregate over a finite window. | `kind=metric`, `service`, `name`, `value`, `tags`, `metric_type`, `aggregation_temporality`, `is_monotonic`, `time_unix_nano` | `resourceMetrics[].resource.attributes`, `scopeMetrics[].metrics[].name`, `sum`, `gauge`, `histogram`, `exponentialHistogram`, `summary`, `dataPoints[].attributes`, `aggregationTemporality`, `isMonotonic` | metric presence, value bounds, units, cardinality, temporality metadata, and scenario evidence |
| resource | Entity metadata shared by spans, logs, or metrics, including service identity. | `service`, `attributes.service.name`, `fields.service.name`, `tags.service.name` | `resource.attributes`, `resource.droppedAttributesCount` | service scoping, ownership, common fields, and provenance of imported evidence |
| scope | Instrumentation library or scope that produced observations. | `scope`, `instrumentation_scope`, `instrumentation_library` | `scopeSpans[].scope`, `scopeMetrics[].scope`, `scopeLogs[].scope`, `instrumentationLibrarySpans[]`, `instrumentationLibraryMetrics[]`, `instrumentationLibraryLogs[]` | import audit context and future static/runtime alignment |
| exemplar | Metric sample that can point back to a trace/span witness. | `exemplars`, `trace_id`, `span_id` | `dataPoints[].exemplars[].traceId`, `dataPoints[].exemplars[].spanId`, `dataPoints[].exemplars[].filteredAttributes` | future cross-signal causality between sampled metrics and traces |
| timestamp | Ordering evidence used to build happens-before checks over finite traces. | `timestamp_ms`, `time_ms`, `start_time_ms`, `end_time_ms`, `timestamp`, `time`, `time_unix_nano`, `start_time_unix_nano`, `end_time_unix_nano` | `startTimeUnixNano`, `endTimeUnixNano`, `timeUnixNano`, `observedTimeUnixNano` | temporal sequence ordering, incident-window grouping, and deadline/window diagnostics |
| attribute | A named value attached to spans, logs, metrics, resources, or exemplars. | `attributes`, `fields`, `tags`, `value` | `attributes[].key`, `attributes[].value`, `filteredAttributes`, `body` | required fields, primitive types, allowed values, regexes, numeric bounds, units, transformations, privacy, and cardinality |
| provenance | Evidence about where an observation came from and how it was normalized. | `_line`, `source`, `source_path`, `normalization`, `import_warnings` | `resource/scope array indexes`, `source JSON path`, `droppedAttributesCount`, `schemaUrl` | bounded claims, reproducibility, skipped-record diagnostics, and auditability of imported collector evidence |

## Satisfaction states

- **present:** A required observation or field exists and all predicates hold.
- **absent:** A required signal or field has no witness in T.
- **malformed:** The contract or evidence cannot be interpreted by the declared domain.
- **partial:** Some evidence exists but required predicates, correlation, ordering, or scenario fields fail.
- **unknown:** The artifact lacks enough modeled evidence to prove the obligation either way; current checker reports this as missing evidence when the contract requires it.
- **transformed:** Evidence is accepted only when its declared transformation is allowed by the privacy/diagnosability policy for that field.

## Observed artifact summary

- Events: 5
- Counts by kind: `{'log': 2, 'metric': 2, 'span': 1}`
- Names by kind: `{'log': ['backup.pg_dump.failed', 'database.destructive_command'], 'metric': ['backup.pg_dump.success', 'postgres.replication.lag_bytes'], 'span': ['disaster_recovery.restore_attempt']}`
- Fields by kind: `{'log': ['actor_role', 'alert_route', 'backup_job_id', 'destination', 'intended_host', 'notification_status', 'target_host', 'target_role'], 'metric': ['backup_job_id', 'database_version', 'destination', 'incident_id', 'primary_host', 'replica_host', 'tool_version'], 'span': ['backup_age_hours', 'source', 'source_environment']}`
- Correlation key counts: `{}`
- Timestamp field counts: `{}`
