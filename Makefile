.PHONY: test smoke lint-contract validate-pass validate-fail static scenario incident-readiness assume-guarantee event-windows refinement composition benchmark taxonomy explain semantics monitor

test:
	python3 -m pytest

smoke: lint-contract validate-pass validate-fail static scenario incident-readiness assume-guarantee event-windows refinement composition benchmark taxonomy explain semantics monitor

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

composition:
	python3 -m telemetry_contracts.cli compose-contract --contract case_studies/gitlab_2017_database_outage/composed_contract.json --format markdown

benchmark:
	python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown

taxonomy:
	python3 -m telemetry_contracts.cli taxonomy --findings reports/current_impact.json --format markdown

explain:
	python3 -m telemetry_contracts.cli explain telemetry.strict_unexpected_field --examples reports/gitlab_2017_strict_validation.json --format markdown

semantics:
	python3 -m telemetry_contracts.cli evaluate-semantics --contract examples/contracts/checkout.contract.json --events examples/telemetry/passing.jsonl --format markdown

monitor:
	python3 -m telemetry_contracts.cli monitor --contract case_studies/gitlab_2017_database_outage/contract.json --events case_studies/gitlab_2017_database_outage/reconstructed_events_sampled_missing_alert.jsonl --format markdown --fail-on never
