# Contract-diff PR report: gitlab.com-database

- Model: `contract-diff-pr-v1`
- Base service: `gitlab.com-database`
- Candidate service: `gitlab.com-database`
- New obligations: 0
- Removed obligations: 1
- Changed privacy classifications: 0
- Changed diagnosability claims: 0
- PR attention required: `true`

## Pull-request review focus

- new required telemetry obligations
- removed required telemetry obligations
- changed privacy classifications or transformations
- changed diagnosability claims

## New obligations

None.

## Removed obligations

| Severity | Path | Message | Details |
| --- | --- | --- | --- |
| warning | `$.logs[name='backup.pg_dump.failed'].fields.alert_delivered` | candidate removes required field `alert_delivered` on log `backup.pg_dump.failed` | `{"fingerprint": "required_field:log:backup.pg_dump.failed:alert_delivered", "id": "log:backup.pg_dump.failed:alert_delivered", "kind": "required_field"}` |

## Changed privacy classifications

None.

## Changed diagnosability claims

None.

## Limitations

- The report compares two finite JSON contracts and does not inspect source-code diffs.
- Predicate meaning is summarized structurally; regex or prose implication is not proved.
- The report is designed for pull-request review triage; use refinement and validation commands for gate-specific checks.
