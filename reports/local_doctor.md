# telemetry-contracts doctor

- Pass: `true`
- OK: 5
- Warnings: 2
- Errors: 0

| Check | Status | Message | Details |
| --- | --- | --- | --- |
| python_version | `ok` | Python version satisfies >=3.10 | `{"executable": "python3.14", "version": "3.14.3"}` |
| optional_yaml_support | `ok` | PyYAML is importable | `{"available": true}` |
| package_install | `warning` | package metadata not found; running from source tree is supported | `{"source_tree": true}` |
| ci_environment | `warning` | No CI environment variables detected; local runs are still valid | `{}` |
| collector_export | `ok` | examples/otlp/collector_coverage_all_signals.otlp.json exists | `{"exists": true, "parent_exists": true, "path": "examples/otlp/collector_coverage_all_signals.otlp.json"}` |
| report_path | `ok` | parent for reports/current_impact.md exists | `{"exists": true, "parent_exists": true, "path": "reports/current_impact.md"}` |
| report_path | `ok` | parent for reports/gitlab_2017_service_owner_sampled.md exists | `{"exists": true, "parent_exists": true, "path": "reports/gitlab_2017_service_owner_sampled.md"}` |

## Limitations

- Doctor validates local CLI assumptions and file paths only; it does not inspect private collector backends.
- YAML support is optional because JSON contracts are the deterministic baseline.

