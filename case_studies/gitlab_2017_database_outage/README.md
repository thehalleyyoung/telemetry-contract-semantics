# GitLab.com 2017 database outage reconstructed fixture

This fixture is **not raw GitLab telemetry**. It is a transparent reconstruction from public incident reports so the benchmark can test whether telemetry contracts would surface diagnosability gaps described in the postmortem.

Sources:

- GitLab, “Postmortem of database outage of January 31,” <https://about.gitlab.com/blog/postmortem-of-database-outage-of-january-31/>
- GitLab, “GitLab.com Database Incident,” <https://about.gitlab.com/blog/2017/02/01/gitlab-dot-com-database-incident/>

Public facts used include replication lag/failure, a destructive operation intended for the secondary but run on the primary, absent pg_dump backups due to a PostgreSQL version mismatch, cron notifications rejected by DMARC, and recovery from a roughly six-hour-old LVM snapshot.

`reconstructed_events_sampled_missing_alert.jsonl` is a deliberately degraded derivative of the reconstructed fixture that simulates a sampled/exported stream missing the backup-failure log. It is used to validate observational-equivalence reporting: the comparison is scoped to whether the `restore-readiness` incident question retains the same minimum evidence, not to byte equality with the original fixture.

Run:

```bash
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
python3 -m telemetry_contracts.cli equivalence \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --left-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --right-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --scenario restore-readiness --format markdown
```
