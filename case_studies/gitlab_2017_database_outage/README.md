# GitLab.com 2017 database outage reconstructed fixture

This fixture is **not raw GitLab telemetry**. It is a transparent reconstruction from public incident reports so the benchmark can test whether telemetry contracts would surface diagnosability gaps described in the postmortem.

Sources:

- GitLab, “Postmortem of database outage of January 31,” <https://about.gitlab.com/blog/postmortem-of-database-outage-of-january-31/>
- GitLab, “GitLab.com Database Incident,” <https://about.gitlab.com/blog/2017/02/01/gitlab-dot-com-database-incident/>

Public facts used include replication lag/failure, a destructive operation intended for the secondary but run on the primary, absent pg_dump backups due to a PostgreSQL version mismatch, cron notifications rejected by DMARC, and recovery from a roughly six-hour-old LVM snapshot.

Run:

```bash
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
```
