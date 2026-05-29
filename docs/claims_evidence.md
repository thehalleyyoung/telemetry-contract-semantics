# Claims and evidence

## What was achieved

- Added a benchmark CLI that runs one or more telemetry contracts against JSONL event corpora and optional diagnosability scenarios.
- Added JSON and Markdown benchmark reports with multi-contract case support, contract/event/source/import-diagnostic counters, finding-by-code/severity, label precision/recall/F1, runtime and per-1K-event metrics, observed memory envelope, import loss rate, dataset metadata, check-type/failure/semantic-feature filters, remediation grouping, and pass/fail metrics.
- Added a reconstructed public historical case study for the GitLab.com 2017 database outage with source citations, fixture metadata, expected findings, and tests.
- Added a current public-code case study for OWASP SecureTea Project `Signin.js` at commit `7a2da8756e6addbe379ae9b23905dcdbe68b3814`, with exact source URL, retrieval date, file SHA, license note, copied MIT-licensed source, labeled findings, and generated reports in `reports/current_impact.json` and `reports/current_impact.md`. It also validates `reconstructed_console_events.jsonl`, a bounded synthetic reconstruction of the same public-code console logging paths, with finite-trace `telemetry.hyper_pii_disclosure` witnesses in `reports/owasp_securetea_hyperproperties.json`.
- Added core schema/static-analysis improvements: finding taxonomy with remediation, sensitivity classification, forbidden-pattern checks, sensitive-value detection, bounded-cardinality policy warnings, source locations, and static rules for sensitive-value logging.
- Added incident-readiness JSON/Markdown reports for the reconstructed GitLab 2017 fixture in `reports/gitlab_2017_incident_readiness.json` and `reports/gitlab_2017_incident_readiness.md`, scoring required evidence, temporal/correlation coverage, privacy risk, remediation completeness, unanswered questions, and top remediation groups.
- Added a finite event-structure model for telemetry traces with parent-child spans, span links, log attachments, metric exemplars, timestamp happens-before edges, concurrent span pairs, and Mermaid incident-window diagrams in service-owner reports and `describe-model` output.
- Added observational-equivalence reports for debugging tasks. `reports/gitlab_2017_observational_equivalence.json` and `.md` compare the GitLab reconstructed fixture with a deliberately degraded sampled/exported derivative by the `restore-readiness` question signature, not by byte equality.
- Added transformation-preservation reports for approved sampling/omission-style changes. `reports/gitlab_2017_transformation_preservation.json` and `.md` check that obligations and selected scenario witnesses satisfied in the reconstructed source trace remain satisfied in the degraded derivative, and report the lost backup-failure alert evidence.
- Added a generated finding-taxonomy artifact in `docs/finding_taxonomy.json` with schema `docs/finding_taxonomy.schema.json`, plus `telemetry-contracts taxonomy` reports that map observed public-fixture findings to category, formal clause, SARIF level, CI baseline keys, and service-owner route. `reports/current_impact_taxonomy.json` and `.md` summarize the taxonomy coverage of the checked-in built-in benchmark report.
- Added executable alternative-obligation semantics: required finite disjunctions over semantically equivalent logs, spans, or metrics, scenario `any_of` adequacy requirements, and GitLab 2017 witness reports in `reports/gitlab_2017_alternative_obligations.json` and `.md`.
- Added strict-mode validation as a closed-world strengthening of runtime satisfaction: `validate --strict` reports unmodeled services, undeclared signal names, unexpected fields, and undocumented collector transformations, while `metadata.strict_validation` provides bounded escape hatches. `reports/gitlab_2017_strict_validation.json` demonstrates the check on a drift derivative of the public GitLab 2017 reconstruction.
- Added `telemetry-contracts explain`, which maps a finding code to its formal clause, operational impact, concrete fix, CI baseline key, and optional observed examples from JSON reports. `reports/gitlab_2017_strict_explain.md` explains `telemetry.strict_unexpected_field` using the checked-in GitLab strict-mode report.
- Added executable small-step contract semantics in `telemetry_contracts.core_semantics` and `telemetry-contracts evaluate-semantics`. `reports/gitlab_2017_semantic_evaluation.json` and `.md` show the GitLab strict drift derivative evaluated by well-formedness, projection, signal, correlation, temporal, alternative, and strict rules, with denotation alignment against `validate_events`.
- Added compiled runtime monitors in `telemetry_contracts.monitor` and `telemetry-contracts monitor`. `reports/gitlab_2017_runtime_monitor.json` and `.md` run deterministic required-signal and temporal-property monitors over the sampled/exported GitLab 2017 derivative, reporting the bounded backup-alert `telemetry.temporal_response` counterexample plus the observed active-group/pending-response memory envelope.
- Added event-window grouping in `telemetry_contracts.windows` and `telemetry-contracts report event-windows`. `reports/gitlab_2017_event_windows.json` and `.md` group the sampled/exported GitLab 2017 derivative by incident id and 2000ms incident slices, localizing event-local findings to ownership windows while keeping missing-signal evidence in `global:contract=all`.
- Added proof-obligation templates in `telemetry_contracts.proof_obligations` and `telemetry-contracts proof-obligations`. `reports/gitlab_2017_proof_obligations.json` and `.md` instantiate well-formedness, satisfaction, preservation, refinement, monitor-soundness, and benchmark-label validity obligations against the GitLab 2017 reconstruction, strict drift derivative, sampled/exported derivative, and built-in benchmark labels.
- Added executable finite-trace temporal properties for safety, bounded response, absence, ordering, and deadlines. `examples/temporal_logic/` contains paired passing/failing fixtures, and `reports/gitlab_2017_temporal_logic_validation.json` shows a bounded `telemetry.temporal_response` finding on the sampled/exported GitLab 2017 derivative when the backup-failure alert witness is removed.
- Added finite-trace hyperproperties for PII non-disclosure and tenant non-interference. `examples/hyperproperties/` contains paired fixtures, and `reports/owasp_securetea_hyperproperties.json` records three bounded `telemetry.hyper_pii_disclosure` witnesses over reconstructed public-code SecureTea console-log telemetry.
- Added assume-guarantee telemetry contracts and reports in `telemetry_contracts.assume_guarantee` and `telemetry-contracts report assume-guarantee`. The GitLab 2017 contract now separates service emission guarantees, collector/exporter assumptions, environment assumptions, and on-call diagnostic obligations; `reports/gitlab_2017_assume_guarantee_sampled.md` records layer-specific counterexamples over the sampled/exported derivative.
- Added executable contract-refinement checking in `telemetry_contracts.refinement` and `telemetry-contracts refinement`. `reports/gitlab_2017_refinement.json` records that the reconstructed GitLab 2017 incident contract refines a checked-in broader baseline fixture, while `reports/gitlab_2017_refinement_weakened.json` records a deliberate weakened candidate with `refinement.required_field_removed`.
- Added contract composition/inheritance in `telemetry_contracts.loader` and `telemetry_contracts.composition`. `case_studies/gitlab_2017_database_outage/composed_contract.json` extends a shared `org_incident_policy.contract.json`; `reports/gitlab_2017_composition.json` records zero parent-refinement findings, and `reports/gitlab_2017_composed_validation.json` validates the resolved contract over the reconstructed public GitLab 2017 fixture.
- Added first-class OTLP JSON/JSONL import coverage for OpenTelemetry collector-style spans, logs, sums, gauges, histograms, exponential histograms, summaries, metric exemplars, span links/events/status, resource/scope metadata, source JSON provenance, alias normalization, importer diagnostics, collector-export risk analysis, and JSONL↔OTLP round-trip conversion. `examples/otlp/collector_mixed_signals.*`, `examples/otlp/collector_stream_aliases.*`, `examples/otlp/collector_coverage_all_signals.*`, `examples/otlp/collector_malformed_records.otlp.jsonl`, `examples/otlp/collector_pipeline_*`, and `examples/benchmarks/partial_otlp.diagnostics.json` are checked-in validation fixtures; the built-in benchmark reports labeled partial-import and collector dropped-evidence/unsupported-feature diagnostics with bounded import loss rates.
- Added bounded OpenTelemetry semantic-convention and local-policy linting in `telemetry_contracts.semconv` and `telemetry-contracts semconv`. `reports/gitlab_2017_semconv_lint.json` and `.md` cite database/metric convention guidance and a contract-local policy requiring `db.system.name="postgresql"` on the reconstructed `postgres.replication.lag_bytes` metric, producing exact remediation over the checked-in GitLab 2017 public reconstruction.
- Added pull-request contract-diff reports in `telemetry_contracts.contract_diff` and `telemetry-contracts contract-diff`. `reports/gitlab_2017_contract_diff.json` and `.md` compare the checked-in GitLab 2017 baseline fixture with a deliberate weakened candidate and flag the removed `alert_delivered` backup-alert obligation with `contract_diff.removed_obligation`. Added `benchmark-diff` for saved benchmark JSON reports, with checked-in example report pairs under `examples/benchmarks/`.

## Bounded novelty claim

This repository now produces a bounded, reproducible telemetry diagnosability/security analysis artifact over public code, public incident-derived data, and checked-in synthetic benchmark fixtures for telemetry semantics. One benchmark run emits labeled findings for a reconstructed GitLab outage diagnosability fixture, a current public OWASP SecureTea source file, a bounded reconstructed SecureTea console-log telemetry fixture, correlation/cardinality/privacy semantics fixtures, a collector-coverage OTLP diagnostic fixture, and a partial-OTLP import diagnostic fixture. The claim is not that "no one else" has found these exact issues or that no comparable private tool exists. The bounded claim is that this repo contains an executable, timestamped, source-cited, deterministic artifact tying telemetry contracts, static anti-pattern checks, labels, import diagnostics, metadata, filters, and generated reports together for these exact public inputs.

### Prior-art/search protocol for the bounded claim

To make the novelty claim falsifiable, use this protocol on or after the retrieval date:

1. Search GitHub and the web for the exact case id `owasp-securetea-signin-current-static-and-hyperproperty`.
2. Search for the exact generated code/path pair `static.secret_logging` and `react_gui/src/views/Signin.js`.
3. Search for the exact phrase `executable telemetry diagnosability contracts` and the GitLab 2017 outage fixture paths.
4. If an earlier public artifact is found that includes the same executable contract/static benchmark, exact public inputs, labels, and generated reports, this bounded novelty claim should be revised.

## What is not proven

- The GitLab fixture is reconstructed from public facts, not original production telemetry.
- The OWASP SecureTea case study is public-code static analysis plus a bounded reconstructed runtime fixture. It is labeled as potential telemetry privacy/security impact in sample code, not a vulnerability disclosure or exploit finding, and the reconstructed runtime values are synthetic placeholders derived from public code paths.
- The contracts and transformation-preservation reports do not prove an incident would have been prevented.
- The small-step semantic evaluator is mechanizable executable semantics aligned against the repository checker on golden fixtures; it is not an independently verified proof assistant development.
- Runtime monitor compilation is deterministic Python over finite JSONL streams and reports observed memory state for the supplied artifact; it is not an independently verified streaming-monitor implementation for every collector ordering or unbounded production workload.
- Event-window grouping is deterministic localization over observed finite event keys and optional time slices. It does not infer private ownership, and event-less findings remain global by design.
- Proof-obligation reports are finite-artifact evidence checklists. They do not prove universal monitor soundness. Executable contract-version refinement is checked separately by `telemetry-contracts refinement`.
- Temporal properties are checked over finite supplied artifacts with explicit timestamps and grouping keys; they do not constitute an unbounded temporal-logic model checker.
- Hyperproperties are checked over finite supplied artifacts and pair/set witnesses; they do not prove universal non-interference or non-disclosure over all executions.
- Assume-guarantee reports check declared layer obligations over finite supplied artifacts; they do not prove organizational accountability or production workflow behavior beyond those artifacts.
- Strict-mode drift findings are over the checked-in finite derivative fixture; they do not imply GitLab emitted those private events or used the modeled collector transformations.
- Semantic-convention linting covers a bounded subset of OpenTelemetry HTTP, database, messaging, and metric-unit guidance plus explicit local policies. It is useful for checked-in artifacts but is not a complete OpenTelemetry compliance suite. OTLP import, collector-export analysis, and round-trip conversion cover JSON/JSONL exports and common signal fields, not protobuf/gRPC ingestion or full backend cardinality.
- Contract-diff reports are structural comparisons of two checked-in contract artifacts for pull-request review. They do not inspect source-code diffs or prove that added/removed obligations are correct for production.
- The benchmark does not establish recall over all possible observability failures. Precision/recall/F1 are measured only against checked-in expected labels for the selected finite cases and filters.
- Static checks are heuristic line/source checks, not full semantic instrumentation analysis.

## Reproducibility protocol

```bash
python3 -m pytest
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format json
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
python3 -m telemetry_contracts.cli analyze-collector-export --input examples/otlp/collector_coverage_all_signals.otlp.json --format markdown
python3 -m telemetry_contracts.cli preservation --contract examples/otlp/collector_pipeline.contract.json --before-events examples/otlp/collector_pipeline_before.jsonl --after-events examples/otlp/collector_pipeline_after.jsonl --format markdown
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --tag privacy --check-type static --format markdown
python3 -m telemetry_contracts.cli benchmark-diff --baseline examples/benchmarks/diff_baseline.report.json --candidate examples/benchmarks/diff_candidate.report.json --format markdown
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
python3 -m telemetry_contracts.cli equivalence \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --left-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --right-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --scenario restore-readiness \
  --format json \
  --output reports/gitlab_2017_observational_equivalence.json
python3 -m telemetry_contracts.cli equivalence \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --left-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --right-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --scenario restore-readiness \
  --format markdown \
  --output reports/gitlab_2017_observational_equivalence.md
python3 -m telemetry_contracts.cli preservation \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --before-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --after-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format json \
  --output reports/gitlab_2017_transformation_preservation.json \
  --fail-on never
python3 -m telemetry_contracts.cli preservation \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --before-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --after-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format markdown \
  --output reports/gitlab_2017_transformation_preservation.md \
  --fail-on never
python3 -m telemetry_contracts.cli taxonomy \
  --format json \
  --output docs/finding_taxonomy.json
python3 -m telemetry_contracts.cli taxonomy \
  --findings reports/current_impact.json \
  --format json \
  --output reports/current_impact_taxonomy.json
python3 -m telemetry_contracts.cli taxonomy \
  --findings reports/current_impact.json \
  --format markdown \
  --output reports/current_impact_taxonomy.md
python3 -m telemetry_contracts.cli report alternative-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format json \
  --output reports/gitlab_2017_alternative_obligations.json
python3 -m telemetry_contracts.cli report alternative-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown \
  --output reports/gitlab_2017_alternative_obligations.md
python3 -m telemetry_contracts.cli report assume-guarantee \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format json \
  --output reports/gitlab_2017_assume_guarantee.json \
  --fail-on never
python3 -m telemetry_contracts.cli report assume-guarantee \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format json \
  --output reports/gitlab_2017_assume_guarantee_sampled.json \
  --fail-on never
python3 -m telemetry_contracts.cli report assume-guarantee \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format markdown \
  --output reports/gitlab_2017_assume_guarantee_sampled.md \
  --fail-on never
python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict \
  --format json \
  --fail-on never > reports/gitlab_2017_strict_validation.json
python3 -m telemetry_contracts.cli explain telemetry.strict_unexpected_field \
  --examples reports/gitlab_2017_strict_validation.json \
  --format markdown \
  --output reports/gitlab_2017_strict_explain.md
python3 -m telemetry_contracts.cli evaluate-semantics \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict \
  --format json \
  --output reports/gitlab_2017_semantic_evaluation.json \
  --fail-on never
python3 -m telemetry_contracts.cli evaluate-semantics \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict \
  --format markdown \
  --output reports/gitlab_2017_semantic_evaluation.md \
  --fail-on never
python3 -m telemetry_contracts.cli monitor \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format json \
  --output reports/gitlab_2017_runtime_monitor.json \
  --fail-on never
python3 -m telemetry_contracts.cli monitor \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format markdown \
  --output reports/gitlab_2017_runtime_monitor.md \
  --fail-on never
python3 -m telemetry_contracts.cli report event-windows \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --dimension incident \
  --incident-slice-ms 2000 \
  --format json \
  --output reports/gitlab_2017_event_windows.json \
  --fail-on never
python3 -m telemetry_contracts.cli report event-windows \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --dimension incident \
  --incident-slice-ms 2000 \
  --format markdown \
  --output reports/gitlab_2017_event_windows.md \
  --fail-on never
python3 -m telemetry_contracts.cli proof-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict \
  --before-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --after-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --benchmark-config benchmarks/builtin.json \
  --format json \
  --output reports/gitlab_2017_proof_obligations.json
python3 -m telemetry_contracts.cli proof-obligations \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl \
  --strict \
  --before-events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --after-events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --benchmark-config benchmarks/builtin.json \
  --format markdown \
  --output reports/gitlab_2017_proof_obligations.md
python3 -m telemetry_contracts.cli semconv \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format json \
  --output reports/gitlab_2017_semconv_lint.json \
  --fail-on never
python3 -m telemetry_contracts.cli semconv \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format markdown \
  --output reports/gitlab_2017_semconv_lint.md \
  --fail-on never
python3 -m telemetry_contracts.cli refinement \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/contract.json \
  --format json \
  --output reports/gitlab_2017_refinement.json
python3 -m telemetry_contracts.cli refinement \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/contract.json \
  --format markdown \
  --output reports/gitlab_2017_refinement.md
python3 -m telemetry_contracts.cli refinement \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/refinement_candidate_weakened_contract.json \
  --format json \
  --output reports/gitlab_2017_refinement_weakened.json \
  --fail-on never
python3 -m telemetry_contracts.cli refinement \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/refinement_candidate_weakened_contract.json \
  --format markdown \
  --output reports/gitlab_2017_refinement_weakened.md \
  --fail-on never
python3 -m telemetry_contracts.cli contract-diff \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/refinement_candidate_weakened_contract.json \
  --format json \
  --output reports/gitlab_2017_contract_diff.json \
  --fail-on never
python3 -m telemetry_contracts.cli contract-diff \
  --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json \
  --candidate-contract case_studies/gitlab_2017_database_outage/refinement_candidate_weakened_contract.json \
  --format markdown \
  --output reports/gitlab_2017_contract_diff.md \
  --fail-on never
python3 -m telemetry_contracts.cli compose-contract \
  --contract case_studies/gitlab_2017_database_outage/composed_contract.json \
  --format json \
  --output reports/gitlab_2017_composition.json
python3 -m telemetry_contracts.cli compose-contract \
  --contract case_studies/gitlab_2017_database_outage/composed_contract.json \
  --format markdown \
  --output reports/gitlab_2017_composition.md
python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/composed_contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl \
  --format json --fail-on never > reports/gitlab_2017_composed_validation.json
python3 -m telemetry_contracts.cli validate \
  --contract examples/temporal_logic/contract.json \
  --events examples/temporal_logic/failing.jsonl \
  --format json \
  --fail-on never > reports/temporal_logic_examples_validation.json
python3 -m telemetry_contracts.cli validate \
  --contract case_studies/gitlab_2017_database_outage/contract.json \
  --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl \
  --format json \
  --fail-on never > reports/gitlab_2017_temporal_logic_validation.json
python3 -m telemetry_contracts.cli validate \
  --contract examples/hyperproperties/contract.json \
  --events examples/hyperproperties/failing.jsonl \
  --format json \
  --fail-on never > reports/hyperproperty_examples_validation.json
python3 -m telemetry_contracts.cli validate \
  --contract case_studies/current/owasp_securetea_signin/contract.json \
  --events case_studies/current/owasp_securetea_signin/reconstructed_console_events.jsonl \
  --format json \
  --fail-on never > reports/owasp_securetea_hyperproperties.json
```

The benchmark passes when all expected labels in `case_studies/gitlab_2017_database_outage/metadata.json`, `case_studies/current/owasp_securetea_signin/metadata.json`, and `benchmarks/builtin.json` match the produced findings and no extra findings appear. The current-impact benchmark records 10 cases, 8 contract-backed cases, 30 runtime events, 35 total labeled findings, and 1.0 precision/recall/F1 for all labeled cases, including 4 `telemetry.hyper_pii_disclosure` findings, collector dropped-evidence/unsupported-feature diagnostics, and a labeled partial-OTLP diagnostic with import loss rate 0.333333. The GitLab temporal validation report records a `telemetry.temporal_response` finding on the degraded sampled/exported derivative. The GitLab assume-guarantee sampled report records 8 layer-partitioned obligations, 3 satisfied, 5 violated, and concrete `ag.*` findings assigning missing evidence to service, collector, and on-call layers while environment evidence is satisfied. The GitLab transformation-preservation report records `pass=false`, 1 event removed, and 6 preservation findings: 2 newly introduced runtime obligation failures including the temporal response, 1 lost scenario signal, and 3 lost scenario fields. The GitLab refinement report records `refines=true` and 0 findings for the reconstructed incident contract against a broader baseline fixture; the weakened-candidate report records `refines=false` and 1 `refinement.required_field_removed` finding. The companion contract-diff report records 1 `contract_diff.removed_obligation` finding for the same removed alert-delivery field. The checked-in semantic-evaluation report records `aligned_with_checker=true`, 7 input events, 6 service-relevant events, 12 small steps, 14 finding signatures, and no denotation mismatches against the deterministic checker. The checked-in proof-obligation report records 27 cataloged feature groups and 99 instantiated obligations over the same bounded public reconstruction artifacts: 82 discharged, 14 violated, and 3 pending refinement templates.
