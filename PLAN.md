# Research Plan: Formal and Practical Telemetry Contracts

## Thesis

Telemetry contracts can be treated as executable specifications for observability: a service satisfies a contract when its traces, metrics, logs, metadata, and transformations provide the evidence needed to diagnose specified production questions while respecting privacy and retention constraints. The research contribution is bounded to deterministic tooling, public/reconstructed datasets, and reproducible benchmarks, not universal claims about all observability systems.

## Formal objects

- **Observations:** spans, logs, metrics, exemplars, resources, scopes, timestamps, attributes, severity, units, and provenance imported from JSONL or OTLP.
- **Traces:** finite partially ordered event structures with causality from parent-child spans, links, timestamps, correlation IDs, and scenario windows.
- **Contracts:** executable specifications containing required observations, field predicates, privacy transformations, temporal requirements, hyperproperties, assumptions, guarantees, and remediation metadata.
- **Findings:** machine-readable violations with severity, category, semantic property, evidence path, remediation, and disclosure sensitivity.
- **Datasets:** synthetic fixtures, real OTLP exports, reconstructed historical incidents, and current public-code case studies with licenses, checksums, labels, and validity threats.

## Semantics

Define contract satisfaction over finite traces. Core predicates include presence, type, unit, range, allowed values, forbidden patterns, correlation, severity, temporal order, scenario answerability, and transformation preservation. Extend the model with temporal logic for safety/response properties, hyperproperties for privacy and tenant isolation, assume-guarantee structure for service/collector/environment obligations, and refinement for organization-wide versus service-specific contracts. Observational equivalence should say when two telemetry streams answer the same debugging question; adequacy should state when available observations are sufficient for a scenario claim.

## Core algorithms

1. **Runtime verification:** index events by kind, name, service, correlation key, and window; evaluate contract clauses deterministically and emit findings.
2. **OTLP normalization:** parse collector exports into the formal observation model while preserving provenance, skipped-record diagnostics, resources, scopes, exemplars, links, and temporality.
3. **Static analysis:** progress from literal matching to AST-aware detectors, bounded string/value abstract interpretation, and path-sensitive fixtures for instrumentation behind branches.
4. **Refinement checking:** compare contracts to detect weakening, incompatible assumptions, missing guarantees, and non-preserving telemetry transformations.
5. **Differential/property testing:** compare JSONL, OTLP import, round-trip conversion, and benchmark labels; fuzz malformed contracts and event streams.

## Evaluation questions

- Can contracts detect missing diagnosability, privacy, correlation, and unit evidence on real or realistic telemetry streams?
- Do static checks catch missing or unsafe instrumentation before runtime without overstating recall?
- Does OTLP import preserve enough semantics to make findings comparable to native JSONL validation?
- How do precision, recall, F1, findings per K events, runtime, memory, and import loss change across benchmark families?
- Which historical incident questions become answerable or remain unanswerable under reconstructed telemetry contracts?
- What validity threats arise from public-code analysis, reconstructed incident data, synthetic labels, and benchmark selection?

## Historical and current datasets

Start from the checked-in GitLab 2017 outage reconstruction and OWASP SecureTea public-code case study. Expand only with source-cited, license-compatible, disclosure-safe artifacts. Every dataset needs metadata for retrieval date, source URL, commit or document version, license, reconstruction status, labels, checksums, responsible-disclosure status, and claims it supports. Current public-code findings should be framed as defensive telemetry quality or privacy anti-patterns, not exploit claims.

## Novelty claims, bounded responsibly

Potential publishable claims should be phrased as artifact claims: the repo provides a deterministic contract language and toolchain connecting formal telemetry semantics, runtime verification, static checks, OTLP import, benchmarks, and reproducible public case studies. Do not claim prevention of incidents, complete recall, vulnerability discovery, or superiority over unknown private systems. Claims must map to tests, fixtures, reports, and explicit limitations.

## Practical integration path

Every formal construct must surface as a user-facing outcome: a CLI flag, checker rule, schema field, finding code, benchmark row, report section, CI/SARIF integration, or dataset template. The minimum practical loop is: author/lint a contract, import or capture telemetry, validate runtime events, run static checks in CI, run scenarios for incident questions, benchmark changes, and archive reports with provenance.

## Milestones

1. **Semantics draft:** formal trace model, contract satisfaction, observational equivalence, and transformation preservation documented against current JSONL behavior.
2. **Language and checker:** composition/refinement, strict mode, optional alternatives, temporal/hyperproperty examples, and taxonomy generation.
3. **OTLP production path:** richer import, streaming, diagnostics, fixtures, collector instructions, and differential tests.
4. **Static analysis path:** AST-aware detectors, abstract-interpretation notes, symbolic/path fixtures, SARIF, and suppressions.
5. **Benchmark suite:** expanded synthetic and reconstructed datasets, validity-threat metadata, report diffing, precision/recall/runtime metrics.
6. **Reproducibility package:** claims-to-evidence matrix, regeneration scripts, replication guide, archival checksums, and release checklist.

## Paper outline

1. Motivation: observability as a correctness property.
2. Formal model: observations, traces, contracts, satisfaction, refinement, and transformations.
3. Toolchain: CLI, validator, static checker, OTLP importer, benchmark harness, and CI/SARIF integration.
4. Case studies: historical incident reconstruction and current public-code analysis with responsible disclosure boundaries.
5. Evaluation: benchmark design, metrics, performance, precision/recall, and validity threats.
6. Related work: runtime verification, temporal logic, event structures, hyperproperties, abstract interpretation, symbolic execution, property-based/differential testing, OpenTelemetry, and observability engineering.
7. Limitations and reproducibility: deterministic scope, non-AI validation, reconstructed data limits, artifact availability, and claim boundaries.
