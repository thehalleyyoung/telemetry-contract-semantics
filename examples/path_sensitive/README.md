# Path-sensitive telemetry fixture

This fixture exercises conditionals, feature flags, retries, exception branches, and fallbacks without claiming production provenance. It documents boundaries for the deterministic checker:

- The `feature_flag=new-payment` branch requires `experiment_id`.
- The retry fallback branch requires `fallback_reason`.
- Exception spans require `exception.type` and boolean `retryable`.
- The temporal sequence catches fallback logs emitted outside the bounded retry window.

False-positive boundary: the checker validates emitted finite telemetry, not source control-flow reachability. False-negative boundary: paths never represented in the supplied trace are unknown unless required by the contract.
