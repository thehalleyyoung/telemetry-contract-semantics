# Observability Report Card — GitHub Action

Add observability scanning to any repository's pull-request checks in three lines
of YAML. The Action scans the telemetry your project already ships for
*missing-evidence* bugs (the questions an on-call engineer cannot answer because
the signal was never emitted), gates the PR on a configurable diagnosability
score and finding severity, uploads findings to the **Security tab** as SARIF,
and posts a concise report as a **PR comment**.

> Observability is a correctness property: under-instrumentation is a detectable
> bug class, not a style preference.

## Quick start

```yaml
name: Observability
on: [pull_request]
permissions:
  contents: read
  security-events: write   # for SARIF upload
  pull-requests: write     # for the PR comment
jobs:
  observability:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: thehalleyyoung/telemetry-contract-semantics@v1
        with:
          path: .
          fail-on: warning
          min-score: 70
```

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `path` | `.` | Directory to scan. |
| `service` | `""` | Restrict analysis to a single service name. |
| `fail-on` | `error` | Fail the check on findings at or above this severity (`error`, `warning`, `never`). |
| `min-score` | `""` | Fail unless the diagnosability score is at least this value (`0`–`100`). Empty disables the score floor. |
| `comment` | `true` | Post the observability report as a PR comment. |
| `upload-sarif` | `true` | Upload findings to the Security tab as SARIF. |
| `token` | `${{ github.token }}` | Token used to post the PR comment. |

## Outputs

| Output | Description |
| --- | --- |
| `score` | The diagnosability score (`0`–`100`), or empty if no telemetry was found. |
| `passed` | Whether the configurable gate passed (`true`/`false`). |
| `findings` | Total number of findings. |

## Permissions

- `security-events: write` — required only when `upload-sarif: true` (GitHub code
  scanning).
- `pull-requests: write` — required only when `comment: true`.
- `contents: read` — to read the checked-out repository.

If you do not want the Security-tab integration or the PR comment, set
`upload-sarif: false` and/or `comment: false` and you can drop the corresponding
permission.

## Diffing against the base branch

To show a score delta (`▲ +8 vs base 74`) in the PR comment, compute a base
report on the base branch and pass it via the underlying CLI:

```yaml
- run: |
    git worktree add ../base ${{ github.event.pull_request.base.sha }}
    python3 -m telemetry_contracts.cli ci-report --path ../base \
      --format json --fail-on never --output base-report.json
    python3 -m telemetry_contracts.cli ci-report --path . \
      --base base-report.json --format markdown --output comment.md
```

## What the gate checks

The pass/fail decision is the union of two configurable rules:

1. **Score floor** — fail if the diagnosability score is below `min-score`.
2. **Severity threshold** — fail if any finding is at or above `fail-on`
   severity (`fail-on: never` disables this rule).

Both are evaluated deterministically from the telemetry your project already
ships; the same inputs always produce the same verdict and the same comment
bytes.

## Underlying command

The Action is a thin wrapper over the CLI; you can run the exact same analysis
locally:

```bash
python3 -m telemetry_contracts.cli ci-report --path . --min-score 70 --fail-on warning
```

## Marketplace description

> **Observability Report Card** — Treat observability as a correctness property.
> This Action scans the telemetry your repository already ships for
> missing-evidence bugs, scores how diagnosable your incidents are out of 100,
> gates pull requests on a score floor and finding severity, surfaces findings in
> the Security tab via SARIF, and comments a crisp report on every PR. Pure,
> deterministic, zero external services.
