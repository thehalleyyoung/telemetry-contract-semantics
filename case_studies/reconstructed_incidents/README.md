# Reconstructed incident telemetry datasets

Disclosure-safe synthetic reconstructions of common observability blind spots. These datasets do not claim to represent any named company's private telemetry. Each subcase separates public facts/general pattern, reconstructed telemetry, source metadata, expected labels, limitations, owner notes, and responsible handling in `metadata.json`, following `case_studies/templates/real_world_fixture_template.json`.

Subcases:

- `queue_backlog_autoscaling_blind_spot`: backlog exists, but autoscaling policy and decision evidence are missing.
- `cache_cdn_purge_failure`: purge failure telemetry omits the cache-key pattern and rollback plan.
- `database_connection_pool_exhaustion`: pool exhaustion log omits max connection and remediation evidence.
- `missing_rollback_evidence`: deployment failure log omits previous-version rollback evidence.
