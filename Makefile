.PHONY: test smoke lint-contract validate-pass validate-fail static scenario incident-readiness assume-guarantee event-windows refinement contract-diff composition benchmark taxonomy sarif ci-gate regenerate-artifacts claims-matrix explain semantics monitor semconv otlp-import collector-analysis collector-preservation

test:
	python3 -m pytest

smoke: lint-contract validate-pass validate-fail static scenario incident-readiness assume-guarantee event-windows refinement contract-diff composition benchmark taxonomy sarif ci-gate regenerate-artifacts claims-matrix explain semantics monitor semconv otlp-import collector-analysis collector-preservation

lint-contract:
	python3 -m telemetry_contracts.cli lint-contract --contract examples/contracts/checkout.contract.json

validate-pass:
	python3 -m telemetry_contracts.cli validate --contract examples/contracts/checkout.contract.json --events examples/telemetry/passing.jsonl

validate-fail:
	python3 -m telemetry_contracts.cli validate --contract examples/contracts/checkout.contract.json --events examples/telemetry/failing.jsonl --fail-on never

static:
	python3 -m telemetry_contracts.cli static --contract examples/contracts/checkout.contract.json examples/services

scenario:
	python3 -m telemetry_contracts.cli scenario --contract examples/contracts/checkout.contract.json --events examples/telemetry/passing.jsonl --id payment-timeout

incident-readiness:
	python3 -m telemetry_contracts.cli report incident-readiness --contract examples/contracts/checkout.contract.json --events examples/telemetry/passing.jsonl --format markdown

assume-guarantee:
	python3 -m telemetry_contracts.cli report assume-guarantee --contract case_studies/gitlab_2017_database_outage/contract.json --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl --format markdown --fail-on never

event-windows:
	python3 -m telemetry_contracts.cli report event-windows --contract case_studies/gitlab_2017_database_outage/contract.json --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl --dimension incident --incident-slice-ms 2000 --format markdown --fail-on never

refinement:
	python3 -m telemetry_contracts.cli refinement --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json --candidate-contract case_studies/gitlab_2017_database_outage/contract.json --format markdown

contract-diff:
	python3 -m telemetry_contracts.cli contract-diff --base-contract case_studies/gitlab_2017_database_outage/refinement_base_contract.json --candidate-contract case_studies/gitlab_2017_database_outage/contract.json --format markdown

composition:
	python3 -m telemetry_contracts.cli compose-contract --contract case_studies/gitlab_2017_database_outage/composed_contract.json --format markdown

benchmark:
	python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown

taxonomy:
	python3 -m telemetry_contracts.cli taxonomy --findings reports/current_impact.json --format markdown

sarif:
	python3 -m telemetry_contracts.cli sarif --findings examples/ci/static_findings.example.json

ci-gate:
	python3 -m telemetry_contracts.cli ci-gate --findings examples/ci/static_findings.example.json --baseline examples/ci/baseline.example.json --format markdown

regenerate-artifacts:
	python3 -m telemetry_contracts.cli regenerate-artifacts --format markdown

claims-matrix:
	python3 -m telemetry_contracts.cli claims-matrix --format markdown

explain:
	python3 -m telemetry_contracts.cli explain telemetry.strict_unexpected_field --examples reports/gitlab_2017_strict_validation.json --format markdown

semantics:
	python3 -m telemetry_contracts.cli evaluate-semantics --contract examples/contracts/checkout.contract.json --events examples/telemetry/passing.jsonl --format markdown

monitor:
	python3 -m telemetry_contracts.cli monitor --contract case_studies/gitlab_2017_database_outage/contract.json --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl --format markdown --fail-on never

semconv:
	python3 -m telemetry_contracts.cli semconv --contract case_studies/gitlab_2017_database_outage/contract.json --events case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl --format markdown --fail-on never

otlp-import:
	python3 -m telemetry_contracts.cli import-otlp --input examples/otlp/collector_coverage_all_signals.otlp.json --output examples/otlp/collector_coverage_all_signals.events.jsonl --diagnostics-output examples/otlp/collector_coverage_all_signals.diagnostics.json

collector-analysis:
	python3 -m telemetry_contracts.cli analyze-collector-export --input examples/otlp/collector_coverage_all_signals.otlp.json --format markdown

collector-preservation:
	python3 -m telemetry_contracts.cli preservation --contract examples/otlp/collector_pipeline.contract.json --before-events examples/otlp/collector_pipeline_before.jsonl --after-events examples/otlp/collector_pipeline_after.jsonl --format markdown
