# Observational-equivalence report: gitlab.com-database

- Model: `observational-equivalence-v1`
- Equivalent: `false`
- Questions compared: 1
- Equivalent questions: 0
- Different questions: 1
- Left events: 5
- Right events: 4

## Relation

Two finite telemetry traces are observationally equivalent for a declared debugging task when the diagnosability answer signature for every selected incident question is identical: the same questions are answerable, the same minimum observations are witnessed, and the same required fields are present or absent. Extra events, event order, concrete values, and byte representation are ignored unless they change that question-level signature.

## Question comparisons

### `restore-readiness`

Can responders identify the intended host, actual host role, destructive command correlation id, backup health, alert delivery, and recovery source freshness?

- Equivalent: `false`
- Left answerable: `false`
- Right answerable: `false`
- Answerability deltas:
  - `log:backup.pg_dump.failed` $signal: left `present`, right `missing`
  - `log:backup.pg_dump.failed` alert_route: left `present`, right `missing`
  - `log:backup.pg_dump.failed` backup_job_id: left `present`, right `missing`
  - `log:backup.pg_dump.failed` destination: left `present`, right `missing`

## Limitations

- Equivalence is scoped to selected contract scenarios and their declared minimum observations.
- This relation compares question answerability signatures, not raw values or byte equality.
- Historical case-study fixtures are reconstructed from public facts when their metadata says so.

