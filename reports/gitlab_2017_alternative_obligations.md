# Alternative-obligations report: gitlab.com-database

- Model: `alternative-obligations-v1`
- Pass: `true`
- Groups: 1
- Required groups: 1
- Satisfied groups: 1
- Unsatisfied required groups: 0

## Relation

A required alternative obligation A is satisfied by finite trace T when at least one declared option has a concrete witness event in T containing every field listed for that option. Optional alternatives document acceptable evidence paths but do not make T fail when no option is witnessed. This is an executable finite disjunction: T ⊨ A iff required(A)=false or ∃ option,witness. option(witness).

## Obligations

### `destructive-command-location-evidence`

- Required: `true`
- Satisfied: `true`
- Winning option: `structured-log`
- Purpose: A destructive-command location witness may be emitted as either a structured log or an equivalent span; one concrete witness avoids duplicate false positives for the absent representation.
- Options:
  - `structured-log` log `database.destructive_command`: satisfied (matches=[1], missing_fields=none)
  - `operation-span` span `database.destructive_command`: missing-signal (matches=[], missing_fields=intended_host, target_host, target_role)

