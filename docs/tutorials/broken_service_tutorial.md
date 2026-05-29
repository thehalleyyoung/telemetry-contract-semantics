# Broken-service telemetry repair tutorial

Use the path-sensitive fixture as a small service whose telemetry is repaired iteratively.

1. Start broken: `python3 -m telemetry_contracts.cli validate --contract examples/path_sensitive/contract.json --events examples/path_sensitive/failing.jsonl --format json --fail-on never`. The failing trace misses feature-flag, fallback, exception, severity, retry-bound, and temporal-window evidence.
2. Fix runtime telemetry: compare with `examples/path_sensitive/passing.jsonl`, which adds `experiment_id`, `fallback_reason`, `exception.type`, boolean `retryable`, WARN fallback severity, and an in-window fallback log.
3. Check source/static issues: `python3 -m telemetry_contracts.cli static --contract case_studies/current/public_static_patterns/contract.json case_studies/current/public_static_patterns --fail-on never`. Add trace/request ids to error logs, bucket user/path labels, avoid raw payload previews, and record exception/status/remediation evidence on error spans.
4. Check OTLP import behavior with `examples/otlp/collector_mixed_signals.otlp.json`, then run `python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown`.

The tutorial is bounded to checked-in public fixtures so every claim is reproducible locally.
