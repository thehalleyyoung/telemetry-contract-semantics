# Claims and evidence

## What was achieved

- Added a benchmark CLI that runs one or more telemetry contracts against JSONL event corpora and optional diagnosability scenarios.
- Added JSON and Markdown benchmark reports with contract, event, source, finding, finding-by-code, finding-by-severity, label precision/recall, runtime, check-type, and pass/fail metrics.
- Added a reconstructed public historical case study for the GitLab.com 2017 database outage with source citations, fixture metadata, expected findings, and tests.
- Added a current public-code case study for OWASP SecureTea Project `Signin.js` at commit `7a2da8756e6addbe379ae9b23905dcdbe68b3814`, with exact source URL, retrieval date, file SHA, license note, copied MIT-licensed source, labeled findings, and generated reports in `reports/current_impact.json` and `reports/current_impact.md`.
- Added core schema/static-analysis improvements: finding taxonomy with remediation, sensitivity classification, forbidden-pattern checks, sensitive-value detection, bounded-cardinality policy warnings, source locations, and static rules for sensitive-value logging.
- Added incident-readiness JSON/Markdown reports for the reconstructed GitLab 2017 fixture in `reports/gitlab_2017_incident_readiness.json` and `reports/gitlab_2017_incident_readiness.md`, scoring required evidence, temporal/correlation coverage, privacy risk, remediation completeness, unanswered questions, and top remediation groups.

## Bounded novelty claim

This repository now produces a bounded, reproducible telemetry diagnosability/security analysis artifact over public code and public incident-derived data: one benchmark run emits labeled findings for a reconstructed GitLab outage diagnosability fixture and for a current public OWASP SecureTea source file. The claim is not that "no one else" has found these exact issues or that no comparable private tool exists. The bounded claim is that this repo contains an executable, timestamped, source-cited, deterministic artifact tying telemetry contracts, static anti-pattern checks, labels, and generated reports together for these exact public inputs.

### Prior-art/search protocol for the bounded claim

To make the novelty claim falsifiable, use this protocol on or after the retrieval date:

1. Search GitHub and the web for the exact case id `owasp-securetea-signin-current-static`.
2. Search for the exact generated code/path pair `static.secret_logging` and `react_gui/src/views/Signin.js`.
3. Search for the exact phrase `executable telemetry diagnosability contracts` and the GitLab 2017 outage fixture paths.
4. If an earlier public artifact is found that includes the same executable contract/static benchmark, exact public inputs, labels, and generated reports, this bounded novelty claim should be revised.

## What is not proven

- The GitLab fixture is reconstructed from public facts, not original production telemetry.
- The OWASP SecureTea case study is public-code static analysis. It is labeled as potential telemetry privacy/security impact in sample code, not a vulnerability disclosure or exploit finding.
- The contracts do not prove an incident would have been prevented.
- The benchmark does not establish recall over all possible observability failures.
- Static checks are heuristic line/source checks, not full semantic instrumentation analysis.

## Reproducibility protocol

```bash
python3 -m pytest
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format json
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
python3 -m telemetry_contracts.cli benchmark \
  --config benchmarks/builtin.json \
  --format json \
  --output reports/current_impact.json
python3 -m telemetry_contracts.cli benchmark \
  --config benchmarks/builtin.json \
  --format markdown \
  --output reports/current_impact.md
python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format json --fail-on never
python3 -m telemetry_contracts.cli static \
  --contract case_studies/current/owasp_securetea_signin/contract.json \
  case_studies/current/owasp_securetea_signin/Signin.js \
  --format json --fail-on never
python3 -m telemetry_contracts.cli report incident-readiness \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --scenario restore-readiness \
  --format json \
  --output reports/gitlab_2017_incident_readiness.json \
  --fail-on never
python3 -m telemetry_contracts.cli report incident-readiness \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --scenario restore-readiness \
  --format markdown \
  --output reports/gitlab_2017_incident_readiness.md \
  --fail-on never
```

The benchmark passes when all expected labels in `case_studies/gitlab_2017_database_outage/metadata.json` and `case_studies/current/owasp_securetea_signin/metadata.json` match the produced findings and no extra findings appear. The current-impact report generated on 2026-05-29 records 3 contracts, 10 runtime events, 14 total labeled findings, and 1.0 precision/recall for the current static case. The GitLab incident-readiness report records 12 findings, 3 missing required-evidence obligations, 3 missing fields for the `restore-readiness` question, and 100% remediation text coverage for those bounded findings.
