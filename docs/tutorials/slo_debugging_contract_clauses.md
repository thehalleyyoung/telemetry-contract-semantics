# Translating SLO debugging questions into contract clauses

This tutorial maps common SLO debugging questions to deterministic telemetry-contract clauses and checked-in passing/failing traces.

| SLO question | Clause style | Passing fixture | Failing fixture | What failure means |
| --- | --- | --- | --- | --- |
| Did checkout emit the evidence needed for a payment timeout? | Scenario minimum observations | `examples/telemetry/passing.jsonl` | `examples/telemetry/failing.jsonl` | Required span/log/field evidence is absent. |
| Did a bad state eventually produce an alert? | Temporal bounded response | `examples/temporal_logic/passing.jsonl` | `examples/temporal_logic/failing.jsonl` | A trigger was observed without a bounded response. |
| Did telemetry disclose private data? | Hyperproperty PII non-disclosure | `examples/hyperproperties/passing.jsonl` | `examples/hyperproperties/failing.jsonl` | A finite witness carries sensitive data to a sink. |
| Can collector assumptions be separated from service guarantees? | Assume-guarantee layer obligations | `case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl` | `case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl` | A layer-specific witness is missing or transformed away. |

Run the rows with `validate`, `scenario`, `report assume-guarantee`, and `benchmark --config benchmarks/builtin.json --format markdown`. These examples are finite-trace checks, not production SLO proof.
