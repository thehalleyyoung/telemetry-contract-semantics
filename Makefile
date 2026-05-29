.PHONY: test smoke lint-contract validate-pass validate-fail static scenario incident-readiness benchmark taxonomy explain

test:
	python3 -m pytest

smoke: lint-contract validate-pass validate-fail static scenario incident-readiness benchmark taxonomy explain

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

benchmark:
	python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown

taxonomy:
	python3 -m telemetry_contracts.cli taxonomy --findings reports/current_impact.json --format markdown

explain:
	python3 -m telemetry_contracts.cli explain telemetry.strict_unexpected_field --examples reports/gitlab_2017_strict_validation.json --format markdown
