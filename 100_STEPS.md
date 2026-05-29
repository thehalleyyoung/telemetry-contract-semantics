# 100 Steps Toward Formal, Practical Telemetry Contracts

This roadmap treats telemetry contracts as executable specifications for production observability. It preserves the 18 verified accomplishments from commit `733080c` while redirecting future work toward formal semantics, program-analysis rigor, reproducible historical/current evidence, and concrete CLI/checker/benchmark outcomes.

## Phase 0 — Verified foundation already present

- [x] 001. Maintain this exact 100-step research roadmap as an executable-project artifact: checkboxes change only after implementation, tests, fixtures, or documentation make the claim reproducible.
- [x] 002. Provide a `lint-contract` CLI path that checks contract shape and schema-level semantics before any telemetry event stream exists.
- [x] 003. Validate malformed contract clauses for invalid field types, non-boolean `required`, malformed `allowed_values`, invalid regexes, impossible numeric bounds, and forbidden-pattern specification errors.
- [x] 004. Publish and test the formal JSON Schema for contract files so the contract language has a machine-checkable syntactic boundary.
- [x] 005. Document the contract lint workflow in the quickstart and architecture overview so formal contract checks remain usable by service teams.
- [x] 006. Run GitHub Actions CI across supported Python versions with tests and smoke checks for the deterministic CLI toolchain.
- [x] 007. Document a responsible-disclosure workflow for privacy-preserving public-code and telemetry findings.
- [x] 008. Preserve OTLP metric semantics for histograms, exponential histograms, summaries, temporality, buckets, quantiles, and timing metadata during import.
- [x] 009. Cover contract lint failures and richer OTLP metric conversion behavior with regression tests.
- [x] 010. Implement cross-signal correlation semantics over traces, logs, and metrics using trace IDs, span IDs, request IDs, or configured correlation keys.
- [x] 011. Implement temporal ordering checks for required span, log, and metric sequences within incident windows.
- [x] 012. Implement conditional requirements, such as requiring `remediation_hint` and `retryable` whenever `error_code` is present.
- [x] 013. Support reusable field dictionaries for shared observability attributes such as tenant ID, trace ID, region, build SHA, and deployment environment.
- [x] 014. Validate log severity policies beyond exact matching, including minimum severity thresholds.
- [x] 015. Validate sampling and retention metadata against machine-readable policy stubs rather than prose-only policy claims.
- [x] 016. Support schema-level privacy classifications with allowed transformations such as redacted, hashed, tokenized, bucketed, or omitted.
- [x] 017. Validate field-level units for durations, bytes, percentages, counts, timestamps, and currency-like values.
- [x] 018. Emit duplicate-signal and duplicate-field diagnostics to catch repeated telemetry definitions during contract linting.

## Phase 1 — Formal model of telemetry and contracts

- [ ] 019. Define a mathematical trace model for spans, logs, metrics, resources, scopes, timestamps, attributes, and OTLP provenance, then map it to the current JSONL event format.
- [ ] 020. Specify contract satisfaction as an executable semantics over finite traces, including total, partial, malformed, and unknown telemetry observations.
- [ ] 021. Model event structures for parent-child spans, span links, log attachment, metric exemplars, and concurrency so causality is explicit instead of inferred only from timestamps.
- [ ] 022. Define observational equivalence and adequacy criteria: when two telemetry streams answer the same diagnosability questions and when missing observations are semantically relevant.
- [ ] 023. Formalize semantic preservation under sampling, retention, redaction, hashing, tokenization, bucketing, and omission transformations, with validator checks for each permitted abstraction.
- [ ] 024. Add temporal-logic documentation and fixtures for safety, liveness-within-window, ordering, absence, and response properties over production telemetry.
- [ ] 025. Add hyperproperty examples for privacy and multi-tenant non-interference, connecting pairs or sets of traces to concrete CLI finding codes.
- [ ] 026. Define assume-guarantee telemetry contracts separating environment assumptions, service emission guarantees, collector assumptions, and on-call diagnostic obligations.
- [ ] 027. Specify contract refinement rules so organization-wide contracts, service contracts, and incident-specific contracts can be compared without weakening required evidence.
- [ ] 028. Document contracts as executable specifications with a small-step or denotational account aligned to the existing deterministic checker behavior.

## Phase 2 — Contract language, refinement, and runtime verification

- [ ] 029. Add contract inheritance or composition for shared organization-wide telemetry requirements, with refinement tests showing composed contracts preserve existing service obligations.
- [ ] 030. Add OpenTelemetry semantic-convention name lint warnings and documentation linking each warning to a concrete convention or local policy.
- [ ] 031. Support optional and alternative signals where one of several semantically equivalent telemetry paths satisfies a requirement.
- [ ] 032. Add event-window grouping so validation can reason per trace, request, tenant, scenario instance, and incident reconstruction slice.
- [ ] 033. Add strict-mode validation that reports unexpected fields, undeclared signal names, and unmodeled services while allowing documented extension points.
- [ ] 034. Generate a machine-readable finding taxonomy from `telemetry_contracts.findings.TAXONOMY`, including severity, category, remediation, disclosure sensitivity, and semantics reference.
- [ ] 035. Add checker support for runtime verification over sliding windows and long-running streams with deterministic bounded-memory summaries.
- [ ] 036. Add a refinement checker that reports weakened requirements, incompatible assumptions, and non-preserving transformations between contracts.

## Phase 3 — OTLP semantics and production data ingestion

- [ ] 037. Import OTLP traces with span parent-child relationships and validate required topology against event-structure contracts.
- [ ] 038. Import OTLP span events and links as first-class observations with causality and provenance fields.
- [ ] 039. Import OTLP resource, scope, and instrumentation-library metadata into normalized fields so contracts can constrain collector and SDK context.
- [ ] 040. Support OTLP JSON exports using abbreviated, legacy, or collector-specific aliases while recording importer provenance and normalization decisions.
- [ ] 041. Preserve structured OTLP log bodies as JSON/object observations instead of stringifying all bodies.
- [ ] 042. Extract OTLP exemplars for metrics and connect exemplars back to traces when IDs are present.
- [ ] 043. Add a streaming OTLP JSONL importer for large collector exports, with documented memory bounds and equivalent validation results to batch import.
- [ ] 044. Add import diagnostics that report skipped malformed OTLP records with JSON paths, reasons, and responsible handling notes.
- [ ] 045. Add a synthetic OTLP fixture suite covering spans, logs, sums, gauges, histograms, exponential histograms, summaries, exemplars, links, events, resources, and scopes.
- [ ] 046. Add real collector export instructions for OpenTelemetry Collector file exporter and vendor-neutral pipelines, then validate the examples in CI smoke tests.
- [ ] 047. Add a converter from telemetry-contracts JSONL back to minimal OTLP JSON for round-trip and differential importer testing.

## Phase 4 — Static program analysis and semantic source checks

- [ ] 048. Replace literal-only static matching with AST-aware detectors where standard-library or lightweight parsers make semantic instrumentation analysis feasible.
- [ ] 049. Add source-language static fixtures for Python, JavaScript, TypeScript, Go, Java, C#, Ruby, and Rust instrumentation examples.
- [ ] 050. Add static checks that resolve telemetry name construction through constants, simple concatenation, template strings, and local wrapper functions.
- [ ] 051. Add static checks for OpenTelemetry API usage patterns including tracer names, meter names, attributes, status codes, metric units, and descriptions.
- [ ] 052. Add static checks for missing exception recording, missing error status, and inconsistent remediation fields on error spans.
- [ ] 053. Add an abstract-interpretation design note and prototype domain for bounded string, attribute-presence, and severity facts used by source checks.
- [ ] 054. Add symbolic-execution-style path fixtures for instrumentation guarded by conditionals, feature flags, and error branches, with explicit false-positive boundaries.
- [ ] 055. Add suppression comments with required justification text, exact source spans, responsible-disclosure flags, and tests proving suppression precision.
- [ ] 056. Add SARIF output for static and runtime findings so GitHub code scanning can consume semantically classified results.
- [ ] 057. Add pre-commit and CI examples for contract linting, static checking, OTLP import smoke tests, and benchmark smoke runs.

## Phase 5 — Benchmarks, validity, and datasets

- [ ] 058. Add benchmark cases for missing correlation IDs across traces, logs, and metrics, with labels tied to temporal/causal semantics.
- [ ] 059. Add benchmark cases for high-cardinality metric labels, privacy/security leaks, and expected warning labels over runtime telemetry and static source.
- [ ] 060. Add benchmark cases for partial OTLP imports with malformed records and expected importer diagnostics.
- [ ] 061. Report benchmark macro metrics including precision, recall, F1, findings per K events, runtime per K events, import loss rate, and memory envelope.
- [ ] 062. Add benchmark report diffing so semantic, performance, and label changes can be compared against a checked-in baseline.
- [ ] 063. Add benchmark metadata for dataset license, provenance, reconstruction status, disclosure status, transformation history, and validity threats.
- [ ] 064. Add benchmark filtering by case ID, tag, check type, dataset, expected failure mode, semantics feature, and disclosure status.
- [ ] 065. Add benchmark Markdown sections listing top remediations grouped by category, severity, affected semantic property, and practical owner.
- [ ] 066. Add a larger synthetic microservices benchmark with checkout, payment, inventory, shipping, auth, notification, queue, and database contracts.
- [ ] 067. Add reconstructed incident datasets for queue backlog/autoscaling blind spots, CDN or cache purge failures, and database connection-pool exhaustion.
- [ ] 068. Add current public-code static case studies for missing correlation fields and high-cardinality labels, with source citations and disclosure-safe summaries.
- [ ] 069. Add a real-world fixture template separating public facts, reconstructed telemetry, labels, provenance, claims, limitations, and responsible handling notes.
- [ ] 070. Add deterministic scripts that regenerate `reports/current_impact.json` and Markdown reports from checked-in contracts, fixtures, and source metadata.
- [ ] 071. Maintain a claims-to-evidence matrix mapping every paper claim to tests, fixtures, benchmark rows, reports, and explicit limitations.

## Phase 6 — Usability, pedagogy, and adoption

- [ ] 072. Add a replication guide with exact commands for every figure, table, benchmark metric, and case-study claim the repo can produce.
- [ ] 073. Add examples showing passing and failing contracts for HTTP APIs, batch jobs, message consumers, cron tasks, and stateful background workers.
- [ ] 074. Add examples translating SLO debugging questions into temporal, causal, and assume-guarantee scenario requirements.
- [ ] 075. Add privacy-safe telemetry design examples for authentication, payments, multi-tenant identifiers, and incident retrospectives.
- [ ] 076. Add examples encoding operational ranges for latency, retry counts, queue depth, saturation, error budgets, and collector drop rates.
- [ ] 077. Add a tutorial that starts with a broken service fixture and incrementally fixes telemetry until validation, scenario checks, and benchmark labels pass.
- [ ] 078. Document contract-authoring anti-patterns, semantic pitfalls, and the precise validator findings users should expect.
- [ ] 079. Document integration with pytest, Make, GitHub Actions, generic CI, artifact upload, SARIF consumers, and responsible-disclosure review.
- [ ] 080. Document importer limitations and unsupported OTLP fields as validity threats rather than hidden implementation gaps.
- [ ] 081. Document finding severity, category, remediation, reproducibility metadata, disclosure sensitivity, and paper-claim relevance.

## Phase 7 — Packaging, APIs, and CLI integration

- [ ] 082. Add package metadata classifiers, project URLs, and long-description validation for PyPI readiness.
- [ ] 083. Add an installed-console-script smoke test proving `telemetry-contracts` works after editable and wheel installation.
- [ ] 084. Add `python -m build` validation and wheel/sdist smoke tests without adding runtime dependencies.
- [ ] 085. Add type-check-friendly public API docs for `load_contract`, `load_jsonl`, `validate_events`, `check_sources`, `import_otlp`, and `run_benchmark`.
- [ ] 086. Add a stable Python API for embedding validation, runtime verification, static checking, and benchmark evaluation without invoking the CLI.
- [ ] 087. Add JSON output schema documentation for findings, import diagnostics, scenario reports, and benchmark reports.
- [ ] 088. Add CLI `--output` support consistently across validate, static, scenario, lint-contract, import, and benchmark commands.
- [ ] 089. Add CLI filtering by severity, code, category, remediation group, semantic property, dataset, and disclosure status.
- [ ] 090. Add CLI `explain` command for a finding code with examples, formal meaning, remediation guidance, and benchmark examples.
- [ ] 091. Add CLI `init` command that scaffolds a service contract, example events, CI snippet, and minimal evaluation metadata.
- [ ] 092. Add CLI `doctor` command checking Python version, optional YAML support, package install state, collector export paths, and writable report paths.

## Phase 8 — Testing, proof obligations, performance, and release discipline

- [ ] 093. Add property-based tests for loader, validator, importer, and contract-refinement edge cases using existing or minimal dependencies.
- [ ] 094. Add differential tests comparing JSONL validation, imported OTLP validation, round-tripped OTLP validation, and expected benchmark labels.
- [ ] 095. Add golden-file tests for CLI JSON, Markdown, SARIF, importer diagnostics, and benchmark report formats.
- [ ] 096. Add performance tests validating at least 100K JSONL events within a documented time and memory budget.
- [ ] 097. Optimize validator matching with indexes by kind, name, service, correlation key, and event window for large traces.
- [ ] 098. Add negative tests proving sensitive previews remain redacted in all CLI, JSON, Markdown, SARIF, and benchmark outputs.
- [ ] 099. Add archival metadata, checksums, retrieval dates, licenses, and reproducible regeneration commands for every public case-study source fixture and generated report.
- [ ] 100. Add a paper-ready limitations section covering static-analysis boundaries, reconstructed-data limits, benchmark validity threats, and deterministic non-AI validation scope.

## Counting invariant

- This file must contain exactly 100 checkbox items.
- Checked items are verified work inherited from the previous roadmap, not aspirational claims.
- Future edits should preserve the mapping from completed implementation to checked roadmap evidence.
