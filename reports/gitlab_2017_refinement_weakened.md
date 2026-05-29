# Contract-refinement report: gitlab.com-database

- Model: `contract-refinement-v1`
- Notation: `C′ ⊑ C`
- Candidate refines base: `false`
- Base service: `gitlab.com-database`
- Candidate service: `gitlab.com-database`
- Findings: 1
- Findings by code: `{"refinement.required_field_removed": 1}`
- Findings by clause: `{"REF.requirement-preservation": 1}`

## Relation

A candidate contract C′ refines a base contract C when every base evidence obligation remains required by C′, predicate changes are strengthening or compatible, privacy and transformation policies are not weakened, and collector/environment/on-call assumptions are not made harder to satisfy.

## Findings

- **error `refinement.required_field_removed`** at `$.logs[name='backup.pg_dump.failed'].fields.alert_delivered`: candidate removed required field 'alert_delivered' from 'backup.pg_dump.failed'

## Evidence summary

- Required signals preserved: 5
- Scenario IDs: `{"added": [], "preserved": ["restore-readiness"], "removed": []}`
- Temporal property IDs: `{"added": [], "preserved": ["backup-failure-alert-within-response-window", "replication-lag-before-destructive-command"], "removed": []}`
- Alternative obligation IDs: `{"added": [], "preserved": ["destructive-command-location-evidence"], "removed": []}`

## Limitations

- The checker is a deterministic finite-contract comparison, not a theorem prover over all possible future contract languages.
- Regex implication and arbitrary predicate implication are conservative: missing inherited predicates are reported, but stronger non-identical regexes are not proved equivalent.
- Historical case-study refinement reports compare checked-in reconstructed contract artifacts, not private production policy evolution.
