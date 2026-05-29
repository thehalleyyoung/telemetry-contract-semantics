.PHONY: test smoke validate-pass validate-fail static scenario benchmark

test:
	python3 -m pytest

smoke: validate-pass validate-fail static scenario benchmark

validate-pass:
	python3 -m telemetry_contracts.cli validate --contract examples/contracts/checkout.contract.json --events examples/telemetry/passing.jsonl

validate-fail:
	python3 -m telemetry_contracts.cli validate --contract examples/contracts/checkout.contract.json --events examples/telemetry/failing.jsonl --fail-on never

static:
	python3 -m telemetry_contracts.cli static --contract examples/contracts/checkout.contract.json examples/services

scenario:
	python3 -m telemetry_contracts.cli scenario --contract examples/contracts/checkout.contract.json --events examples/telemetry/passing.jsonl --id payment-timeout

benchmark:
	python3 -m telemetry_contracts.cli benchmark --config benchmarks/builtin.json --format markdown
