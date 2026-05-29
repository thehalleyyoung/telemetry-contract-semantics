# 100 Steps Toward Semantically Grounded, Immediately Useful Telemetry Contracts

This roadmap treats telemetry contracts as executable program-semantics artifacts: a contract denotes obligations over finite, partially ordered telemetry traces, and the tool decides whether concrete service, collector, and source-code evidence satisfies those obligations. Every future item must deliver an immediate user-facing artifact as well as a formal-methods contribution. The 33 checked items are preserved as already implemented and tested capabilities; unchecked items are aspirational until backed by code, fixtures, tests, reports, or documentation.

## Phase 0 — Verified foundation already present

- [x] 001. Maintain this exact 100-step roadmap as a release artifact whose checkbox state is changed only when reproducible implementation, tests, reports, or documentation justify the claim.
- [x] 002. Provide a drop-in `lint-contract` CLI path that checks contract shape before telemetry exists, giving teams immediate CI feedback and a syntactic boundary for the contract language.
- [x] 003. Validate malformed clauses for invalid field types, non-boolean `required`, malformed `allowed_values`, invalid regexes, impossible numeric bounds, and forbidden-pattern errors, grounding early failures in executable well-formedness rules.
- [x] 004. Publish and test the JSON Schema for contract files so contract syntax is machine-checkable and editors/CI can reject non-contract artifacts deterministically.
- [x] 005. Document the lint workflow in quickstart and architecture docs so service owners can adopt semantic contract checks without reading the implementation.
- [x] 006. Run GitHub Actions CI across supported Python versions with tests and smoke checks, establishing the baseline regression gate for the deterministic toolchain.
- [x] 007. Document responsible-disclosure handling for telemetry privacy findings so public-code and public-data analyses have operational guardrails.
- [x] 008. Preserve OTLP metric semantics for histograms, exponential histograms, summaries, temporality, buckets, quantiles, and timing metadata during import.
- [x] 009. Cover contract lint failures and richer OTLP metric conversion behavior with regression tests, making those semantic preservation claims repeatable.
- [x] 010. Implement cross-signal correlation checks over traces, logs, and metrics using trace IDs, span IDs, request IDs, or configured correlation keys.
- [x] 011. Implement temporal ordering checks for required span, log, and metric sequences within incident windows.
- [x] 012. Implement conditional requirements such as requiring `remediation_hint` and `retryable` whenever `error_code` is present.
- [x] 013. Support reusable field dictionaries for shared attributes such as tenant ID, trace ID, region, build SHA, and deployment environment.
- [x] 014. Validate log severity policies beyond exact matching, including minimum severity thresholds.
- [x] 015. Validate sampling and retention metadata against machine-readable policy stubs rather than prose-only policy claims.
- [x] 016. Support schema-level privacy classifications with allowed transformations such as redacted, hashed, tokenized, bucketed, or omitted.
- [x] 017. Validate field-level units for durations, bytes, percentages, counts, timestamps, and currency-like values.
- [x] 018. Emit duplicate-signal and duplicate-field diagnostics to catch repeated telemetry definitions during contract linting.

## Phase 1 — Executable core semantics with practical diagnostics

- [x] 019. Define the observation domain for spans, logs, metrics, resources, scopes, exemplars, timestamps, attributes, and provenance, then expose a `describe-model` CLI page that maps each object to existing JSONL and OTLP fields.
- [x] 020. Specify the contract satisfaction relation `trace ⊨ contract` for present, absent, malformed, partial, unknown, and transformed observations, then attach each validator finding code to one violated semantic clause.
- [x] 021. Model traces as finite event structures with parent-child spans, links, log attachment, metric exemplars, happens-before, and concurrency, then produce incident-window diagrams in service-owner reports.
- [x] 022. Define diagnosability adequacy: the minimum observations needed to answer an incident question, then report unanswered questions and the exact missing evidence in CI artifacts.
- [x] 023. Define observational equivalence for debugging tasks so sampled, scrubbed, or aggregated streams can be compared by the questions they still answer, not by byte equality.
- [x] 024. Formalize semantic preservation for redaction, hashing, tokenization, bucketing, omission, sampling, retention, and aggregation, then fail contracts when an approved transformation destroys required diagnosability or privacy evidence.
- [x] 025. Add a mechanizable small-step or denotational semantics for contract evaluation and align it with the deterministic checker through golden traces.
- [x] 026. Add proof-obligation templates for every contract feature: well-formedness, satisfaction, preservation, refinement, monitor soundness, and benchmark-label validity.
- [x] 027. Add temporal-logic examples for safety, bounded response, absence, ordering, and deadline properties, each paired with a failing and passing telemetry fixture.
- [x] 028. Add hyperproperty examples for PII non-disclosure and tenant non-interference over pairs or sets of traces, each producing actionable privacy-risk findings.
- [ ] 029. Define assume-guarantee contracts that separate service emission guarantees, collector/exporter assumptions, environment assumptions, and on-call diagnostic obligations.
- [ ] 030. Define contract refinement so organization, team, service, and incident-specific contracts can be compared for weakening, strengthening, and compatible assumptions.

## Phase 2 — Contract language and runtime monitors that teams can gate in CI

- [ ] 031. Add contract composition or inheritance for shared organization policies, with refinement tests proving service contracts do not silently weaken required evidence.
- [x] 032. Add optional and alternative signal obligations so semantically equivalent evidence paths can satisfy the same diagnosability requirement without duplicate false positives.
- [x] 033. Add strict-mode validation for unexpected fields, undeclared signal names, unmodeled services, and undocumented collector transformations, with documented escape hatches.
- [x] 034. Generate a machine-readable finding taxonomy with severity, category, formal clause, remediation, disclosure sensitivity, service owner, and CI/SARIF mapping.
- [ ] 035. Add monitor compilation from contract clauses to bounded-memory runtime checks over finite traces and sliding windows, with determinism tests.
- [ ] 036. Add event-window grouping by trace, request, tenant, deployment, scenario instance, and incident slice so findings are localized to actionable ownership units.
- [ ] 037. Add OpenTelemetry semantic-convention linting that cites the relevant convention or local policy and proposes the exact attribute/name remediation.
- [ ] 038. Add a refinement checker that reports weakened requirements, incompatible assumptions, and non-preserving telemetry transformations between two contract versions.
- [ ] 039. Add contract-diff reports for pull requests showing new obligations, removed obligations, changed privacy classifications, and changed diagnosability claims.
- [ ] 040. Add regression-gated CI examples that fail on new high-severity findings while allowing audited baseline findings with expiration and owner metadata.
- [x] 041. Add incident-readiness reports that score each service on required evidence, temporal coverage, correlation coverage, privacy risk, and remediation completeness.
- [x] 042. Add a CLI `explain` command that turns each finding into its formal meaning, practical impact, example traces, and concrete fix.

## Phase 3 — OTLP collector export semantics and production ingestion

- [ ] 043. Import OTLP traces with parent-child relationships, links, span events, status, attributes, resources, scopes, and instrumentation metadata as first-class event-structure evidence.
- [ ] 044. Preserve OTLP log body structure, severity, trace/span attachment, resource metadata, and observed-time semantics without stringifying away required fields.
- [ ] 045. Extract OTLP metric exemplars and connect them to traces when IDs are present, enabling cross-signal causality checks for sampled production exports.
- [ ] 046. Support abbreviated, legacy, and collector-specific OTLP JSON aliases while recording normalization decisions and source JSON paths for auditability.
- [ ] 047. Add a streaming OTLP JSONL importer for large collector file-exporter output, with documented memory bounds and equivalence tests against batch import.
- [ ] 048. Add import diagnostics for skipped malformed records with JSON path, reason, severity, provenance, and whether the skip can invalidate a contract claim.
- [ ] 049. Add a collector-export analysis command that summarizes dropped fields, unknown schemas, cardinality risks, PII/secret risks, temporality, and unsupported OTLP features.
- [ ] 050. Add vendor-neutral OpenTelemetry Collector file-exporter instructions and CI smoke fixtures so teams can validate real exports without vendor lock-in.
- [ ] 051. Add an OTLP-to-contract JSONL round-trip converter for differential testing of importer semantics and regression analysis.
- [ ] 052. Add fixtures covering spans, logs, sums, gauges, histograms, exponential histograms, summaries, exemplars, links, events, resources, scopes, temporality, and malformed records.
- [ ] 053. Add collector-pipeline preservation checks proving scrubbing, sampling, aggregation, and routing steps preserve the contract properties they claim to preserve.

## Phase 4 — Static analysis as abstract interpretation of instrumentation code

- [ ] 054. Replace literal-only static matching with AST-aware detectors for supported languages, reporting source spans and the semantic contract obligation each span attempts to discharge.
- [ ] 055. Add source fixtures for Python, JavaScript, TypeScript, Go, Java, C#, Ruby, and Rust that cover spans, logs, metrics, attributes, wrappers, constants, and error paths.
- [ ] 056. Resolve telemetry names and attributes through constants, local wrappers, simple concatenation, template strings, and common OpenTelemetry helper APIs.
- [ ] 057. Add OpenTelemetry API usage checks for tracer names, meter names, span status, exception recording, metric units, descriptions, and semantic-convention attributes.
- [ ] 058. Define and prototype abstract domains for bounded strings, attribute presence, severity, units, privacy class, and path feasibility, with explicit join/widening behavior.
- [ ] 059. Add path-sensitive fixtures for conditionals, feature flags, retries, exception branches, and fallbacks, documenting false-positive and false-negative boundaries.
- [ ] 060. Add static checks for missing exception recording, missing error status, absent remediation fields, inconsistent retryability, and uncorrelated error logs.
- [ ] 061. Add PII/secret telemetry risk checks for likely credentials, tokens, emails, phone numbers, tenant identifiers, raw payloads, and unsafe preview fields in source and event streams.
- [ ] 062. Add suppression comments requiring justification, owner, expiry, exact finding code, source span, and disclosure sensitivity, with tests proving suppression precision.
- [ ] 063. Add SARIF output for static and runtime findings so GitHub code scanning can display semantic categories, remediation text, and responsible owners.
- [ ] 064. Add pre-commit, Make, GitHub Actions, and generic CI examples for linting contracts, checking sources, importing OTLP, and smoke-running benchmarks.

## Phase 5 — Benchmarks, datasets, and validity as first-class claims

- [ ] 065. Add benchmark cases for missing correlation across traces, logs, and metrics, with labels tied to causal/event-structure semantics and incident-readiness impact.
- [ ] 066. Add benchmark cases for high-cardinality labels, PII/secret leaks, unsafe transformations, and expected remediation categories across runtime telemetry and source code.
- [ ] 067. Add benchmark cases for partial OTLP imports, malformed records, collector drops, unsupported fields, and expected diagnostics that bound claim validity.
- [ ] 068. Report precision, recall, F1, findings per K events, runtime per K events, memory envelope, import loss rate, and diagnosability-score changes per benchmark family.
- [ ] 069. Add benchmark report diffing so pull requests show changed labels, changed performance, changed semantic coverage, and changed top remediation groups.
- [ ] 070. Add dataset metadata for source URL, retrieval date, commit/document version, license, checksum, reconstruction status, disclosure status, transformations, labels, and validity threats.
- [ ] 071. Add benchmark filtering by case ID, tag, check type, dataset, expected failure mode, semantics feature, service owner, and disclosure status.
- [ ] 072. Add Markdown and JSON report sections listing top remediations grouped by severity, semantic property, affected owner, estimated effort, and incident-readiness benefit.
- [ ] 073. Add a larger synthetic microservices benchmark covering checkout, payment, inventory, shipping, auth, notification, queue, cache, database, and collector contracts.
- [ ] 074. Add reconstructed incident datasets for queue backlog/autoscaling blind spots, cache/CDN purge failures, database connection-pool exhaustion, and missing rollback evidence.
- [ ] 075. Add current public-code static case studies for missing correlation, high-cardinality labels, unsafe payload logging, and incomplete error spans, with citations and disclosure-safe summaries.
- [ ] 076. Add real-world fixture templates that separate public facts, reconstructed telemetry, source metadata, labels, claims, limitations, owner notes, and responsible handling.
- [ ] 077. Add deterministic regeneration commands for `reports/current_impact.json`, benchmark Markdown, service-owner reports, and paper tables from checked-in artifacts.
- [ ] 078. Maintain a claims-to-evidence matrix mapping every README, PLAN, report, and paper claim to tests, fixtures, benchmark rows, commits, and explicit limitations.

## Phase 6 — User workflows that convert formal evidence into operational value

- [ ] 079. Add a `telemetry-contracts init` workflow that scaffolds a service contract, example events, CI gate, owner metadata, and initial incident-readiness report.
- [ ] 080. Add service-owner reports that summarize contract coverage, failing obligations, privacy risks, collector/export problems, remediation priority, and links to source spans.
- [ ] 081. Add diagnosability scorecards for HTTP APIs, batch jobs, message consumers, cron tasks, and stateful workers, each backed by formal adequacy criteria.
- [ ] 082. Add tutorials translating SLO debugging questions into temporal, causal, hyperproperty, and assume-guarantee contract clauses with passing/failing traces.
- [ ] 083. Add privacy-safe telemetry design examples for authentication, payments, tenant isolation, incident retrospectives, support workflows, and audit trails.
- [ ] 084. Add examples encoding operational ranges for latency, retry count, queue depth, saturation, error budgets, collector drop rates, and sampling budgets.
- [ ] 085. Add a broken-service tutorial that iteratively fixes telemetry until contract validation, static checks, OTLP import, scenario checks, and benchmarks pass.
- [ ] 086. Document authoring anti-patterns such as ambiguous names, unit-free metrics, unbounded cardinality, PII previews, timestamp-only causality, and prose-only remediation.
- [ ] 087. Document integration with pytest, Make, GitHub Actions, generic CI, artifact upload, SARIF consumers, incident review, and responsible-disclosure review.
- [ ] 088. Document importer limitations and unsupported OTLP fields as validity threats surfaced in reports rather than hidden implementation caveats.

## Phase 7 — APIs, packaging, and reproducible research artifacts

- [ ] 089. Add package metadata classifiers, project URLs, long-description validation, and wheel/sdist smoke tests for PyPI-quality distribution.
- [ ] 090. Add installed-console-script smoke tests proving `telemetry-contracts` works after editable install and wheel installation.
- [ ] 091. Add type-check-friendly public API docs for `load_contract`, `load_jsonl`, `validate_events`, `check_sources`, `import_otlp`, `run_benchmark`, and report generation.
- [ ] 092. Add a stable Python API for embedding validation, runtime monitoring, static checking, OTLP import, benchmark evaluation, and service-owner reporting without shelling out.
- [ ] 093. Add JSON Schema documentation for findings, import diagnostics, scenario reports, benchmark reports, service-owner reports, and claims-to-evidence matrices.
- [ ] 094. Add consistent CLI `--output`, `--format`, and filtering support across validate, static, scenario, lint-contract, import, benchmark, report, and explain commands.
- [ ] 095. Add a `doctor` command that checks Python version, optional YAML support, package install state, collector export paths, report paths, and CI environment assumptions.
- [ ] 096. Add a replication guide with exact commands for every figure, table, benchmark metric, historical analysis, current case-study claim, and report artifact.

## Phase 8 — Testing, proof obligations, performance, and release discipline

- [ ] 097. Add property-based and differential tests for loaders, validators, importers, monitors, refinement, transformations, and benchmark labels using existing or minimal dependencies.
- [ ] 098. Add golden-file tests for CLI JSON, Markdown, SARIF, importer diagnostics, service-owner reports, incident-readiness reports, and benchmark report formats.
- [ ] 099. Add performance tests validating at least 100K JSONL events and large OTLP exports within documented time and memory budgets, then optimize indexes by kind, name, service, correlation key, and window.
- [ ] 100. Add a paper-ready limitations and release checklist covering mechanized-core scope, static-analysis boundaries, reconstructed-data limits, benchmark validity threats, privacy safeguards, archival metadata, checksums, and deterministic non-AI validation.

## Counting invariant

- This file must contain exactly 100 Markdown checkbox items.
- Checked items are verified work inherited from the previous roadmap, not aspirational claims.
- Future edits should preserve the mapping from implemented behavior to checked roadmap evidence.
