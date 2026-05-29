# Semantic-convention lint report

- Pass: `true`
- Events checked: 5
- Findings: 7
- Findings by code: `{"semconv.local_policy": 2, "semconv.metric_unit": 1, "semconv.missing_attribute": 4}`
- Findings by severity: `{"warning": 7}`

## Policy sources
- OpenTelemetry HTTP semantic conventions: request/response attributes such as http.request.method, http.route, and http.response.status_code.
- OpenTelemetry database semantic conventions: database attributes such as db.system.name, db.operation.name, db.namespace, db.collection.name, server.address, and db.query.text.
- OpenTelemetry messaging semantic conventions: messaging.system, messaging.destination.name, and messaging.operation.name.
- OpenTelemetry metrics guidance: declare measurement units separately from metric identity when possible.
- Contract metadata.semantic_conventions local policy entries checked as artifact-scoped extensions.

## Findings
| Severity | Code | Location | Remediation | Convention/local policy |
| --- | --- | --- | --- | --- |
| warning | `semconv.missing_attribute` | `$.metrics[0].fields.db.system.name` | Add 'db.system.name' to the contract and emit it on 'postgres.replication.lag_bytes'. | OpenTelemetry database semantic conventions identify database technology with db.system.name. |
| warning | `semconv.metric_unit` | `$.metrics[0].value.unit` | Declare value.unit 'By' and consider renaming the metric to 'postgres.replication.lag'. | OpenTelemetry metric semantic conventions prefer explicit units in instrument metadata over unit-only name suffixes. |
| warning | `semconv.missing_attribute` | `$.logs[0].fields.db.system.name` | Add 'db.system.name' to the contract and emit it on 'database.destructive_command'. | OpenTelemetry database semantic conventions identify database technology with db.system.name. |
| warning | `semconv.local_policy` | `$.metadata.semantic_conventions.required_attributes[0].attribute` | Add db.system.name="postgresql" to the postgres.replication.lag_bytes contract and emitted metric tags. | OpenTelemetry database semantic conventions identify database technology with db.system.name; this local reconstruction policy requires postgresql on PostgreSQL replication telemetry. |
| warning | `semconv.missing_attribute` | `event[1].db.system.name` | Emit 'db.system.name' on 'postgres.replication.lag_bytes' or document a local policy exception. | OpenTelemetry database semantic conventions identify database technology with db.system.name. |
| warning | `semconv.missing_attribute` | `event[2].db.system.name` | Emit 'db.system.name' on 'database.destructive_command' or document a local policy exception. | OpenTelemetry database semantic conventions identify database technology with db.system.name. |
| warning | `semconv.local_policy` | `event[1].db.system.name` | Add db.system.name="postgresql" to the postgres.replication.lag_bytes contract and emitted metric tags. | OpenTelemetry database semantic conventions identify database technology with db.system.name; this local reconstruction policy requires postgresql on PostgreSQL replication telemetry. |

