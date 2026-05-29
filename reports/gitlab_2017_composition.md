# Contract-composition report: gitlab.com-database

- Model: `contract-composition-v1`
- Notation: `C = P₁ ⊕ … ⊕ Pₙ ⊕ Δ`
- Has inherited policies: `true`
- Composition valid: `true`
- Direct parents: 1
- Inherited signals: 5
- Declared signals: 5
- Resolved signals: 5
- Overridden signals: 5
- Findings by code: `{}`

## Relation

A composed contract is the left-to-right merge of inherited organization/team policies and the service delta. Each parent policy must be refined by the resolved child contract, so inherited required evidence, privacy policies, strict-mode assumptions, temporal/scenario obligations, and assume-guarantee clauses are not silently weakened.

## Inheritance evidence

- Inherited signal keys: `["log:backup.pg_dump.failed", "log:database.destructive_command", "metric:backup.pg_dump.success", "metric:postgres.replication.lag_bytes", "span:disaster_recovery.restore_attempt"]`
- Declared signal keys: `["log:backup.pg_dump.failed", "log:database.destructive_command", "metric:backup.pg_dump.success", "metric:postgres.replication.lag_bytes", "span:disaster_recovery.restore_attempt"]`
- Overridden signal keys: `["log:backup.pg_dump.failed", "log:database.destructive_command", "metric:backup.pg_dump.success", "metric:postgres.replication.lag_bytes", "span:disaster_recovery.restore_attempt"]`

## Parent refinement checks

- `case_studies/gitlab_2017_database_outage/org_incident_policy.contract.json` refines parent: `true`; findings: 0

## Findings

No parent-refinement violations were found.

## Limitations

- Composition is finite JSON/YAML contract inheritance; it is not a theorem prover for arbitrary policy languages.
- Weakening detection reuses the deterministic refinement checker, whose predicate implication checks are conservative for regexes and arbitrary predicates.
- Historical case-study composition reports validate checked-in reconstructed contracts and public facts, not private production policy history.
