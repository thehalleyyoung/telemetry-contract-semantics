# Limitations and release checklist

Use this checklist before publishing a release, paper artifact, or generated report bundle.

## Scope limitations

- [ ] Mechanized core: state that executable semantics are deterministic Python aligned with tests, not a proof-assistant mechanization.
- [ ] Static analysis: disclose Python AST plus lightweight multi-language heuristics, not whole-program interprocedural analysis.
- [ ] Reconstructed data: label GitLab and console-log fixtures as reconstructed from public facts or public code, not original production telemetry.
- [ ] Benchmark validity: report precision/recall only against checked-in labels and finite fixtures.
- [ ] Privacy safeguards: keep sensitive previews redacted and route responsible-disclosure-sensitive findings to owners.
- [ ] Importer limits: surface malformed records, dropped evidence, unsupported OTLP metrics/fields, and JSON/JSONL-only ingestion.
- [ ] Archival metadata: include source URL, retrieval date, version/commit, license, checksums, and transformation notes.
- [ ] Deterministic non-AI validation: document exact commands; do not claim LLM-dependent verification.

## Release gates

```bash
python3 -m pytest -q
make smoke
python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
python3 -m telemetry_contracts.cli claims-matrix --format markdown
python3 -m telemetry_contracts.cli doctor --collector-export examples/otlp/collector_coverage_all_signals.otlp.json --report-path reports/current_impact.md --format markdown
```

The release is ready only when generated claims are backed by checked-in fixtures, schemas/docs are updated, and `100_STEPS.md` remains ignored and untracked.
