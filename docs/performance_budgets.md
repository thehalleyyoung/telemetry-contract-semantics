# Performance budgets

The deterministic checker is validated on generated in-memory fixtures in `tests/test_performance.py`:

- 100,000 JSONL-shaped events indexed by kind, name, service, correlation key, and 1s window should validate under a generous 20 second local budget.
- A large OTLP export with 3,000 spans, 3,000 metrics, and 3,000 logs should import and analyze under a generous 20 second local budget.

These are regression budgets for the prototype and CI-sized fixtures, not production throughput claims. Benchmark reports expose runtime, per-1K-event, and memory-envelope counters for checked-in corpora.
