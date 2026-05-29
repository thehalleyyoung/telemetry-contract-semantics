#!/usr/bin/env sh
set -eu

python3 -m telemetry_contracts.cli validate \
  --contract examples/contracts/checkout.contract.json \
  --events examples/telemetry/passing.jsonl \
  --format sarif > telemetry-contracts.validate.sarif

python3 -m telemetry_contracts.cli static \
  --contract examples/contracts/checkout.contract.json \
  examples/services \
  --format json > telemetry-contracts.static.json

python3 -m telemetry_contracts.cli ci-gate \
  --findings telemetry-contracts.static.json \
  --baseline examples/ci/baseline.example.json \
  --fail-on error
