# Transformation-preservation report: checkout-api

- Model: `transformation-preservation-v1`
- Preserves selected obligations: `true`
- Approved transformations: `aggregation, redaction, routing, sampling`
- Source events: 4
- Transformed events: 3
- Events removed: 1
- Scenarios checked: 1
- Preservation findings: 0
- Findings by code: `{}`

## Relation

For a contract C, source trace T, transformed trace T′, and approved transformations Δ, T′ preserves C when every runtime contract obligation and diagnosability witness that is satisfied in T remains satisfied in T′. The check is obligation-local: it reports newly destroyed evidence even when T already violates unrelated obligations.

## Preservation findings

No preservation regressions were found for selected obligations.

## Scenario preservation

### `collector-preserves-checkout`

- Source answerable: `true`
- Transformed answerable: `true`
- Lost witnesses: 0

## Limitations

- The relation is scoped to this contract's declared signals, field predicates, privacy transformations, and selected scenarios.
- The checker compares finite artifacts; it does not prove a collector implementation correct for all possible production traces.
- Historical case-study fixtures are reconstructed when their metadata says so; preservation claims are bounded to checked-in artifacts.

