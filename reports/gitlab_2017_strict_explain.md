# Finding explanation: `telemetry.strict_unexpected_field`

- Category: `schema`
- Default severity: `error`
- Formal clause: `STRICT.field-closed-world`
- SARIF level: `error`
- Service owner route: contract service owner
- Disclosure sensitivity: `internal`

## Formal meaning

`STRICT.field-closed-world` is a closed-world strict-mode side condition on T ⊨ C. The deterministic checker emits this finding when the corresponding schema obligation has a finite counterexample or missing witness.

## Practical impact

Emitted telemetry no longer matches the modeled data domain, which can break dashboards, alerts, joins, or strict drift gates.

## Example trace shape

1. contract C with strict mode
2. finite telemetry trace T
3. check closed-world service, signal, field, and transformation side conditions

## Concrete fix

Declare the emitted field on the signal contract or add an explicit strict allowed_extra_fields escape hatch.

## CI / baseline key

- Default fail-on: `error`
- Baseline key fields: `["code", "path", "contract_path", "event_index"]`

## Observed examples

| Source | Severity | Path | Event index | Message |
| --- | --- | --- | ---: | --- |
| reports/gitlab_2017_strict_validation.json | error | event[1].tags.collector_pipeline | 1 | metric 'postgres.replication.lag_bytes' emitted undeclared field 'collector_pipeline' |
| reports/gitlab_2017_strict_validation.json | error | event[4].fields.notification_status | 4 | log 'backup.pg_dump.failed' emitted undeclared field 'notification_status' |

## Bounded evidence claim

For the supplied artifacts, `telemetry.strict_unexpected_field` appears 2 time(s) across 1 source report(s): reports/gitlab_2017_strict_validation.json. This does not claim completeness beyond those checked-in finite reports.

