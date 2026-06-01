#!/usr/bin/env bash
# One-command reproduction for artifact evaluation.
#
# Regenerates every offline figure, table, and headline number from the frozen
# inputs and verifies them against the committed SHA-256 determinism manifest.
# Pure stdlib + git; no network required for the offline reproduction.
#
# Usage:
#   docs/artifact_evaluation/reproduce.sh          # regenerate + write manifest
#   docs/artifact_evaluation/reproduce.sh --check  # regenerate + verify (CI mode)
set -euo pipefail

cd "$(dirname "$0")/../.."

PY="${PYTHON:-python3}"

echo "==> Python: $($PY --version)"
echo "==> Running the offline test suite"
$PY -m pytest -q -o addopts="" -p no:benchmark

if [ "${1:-}" = "--check" ]; then
  echo "==> Verifying artifacts against the committed determinism manifest"
  $PY -m telemetry_contracts.cli reproduce --check
  echo "==> OK: all artifacts match the committed manifest"
else
  echo "==> Regenerating all offline artifacts and writing the manifest"
  $PY -m telemetry_contracts.cli reproduce --write
  echo "==> Wrote reports/reproduce_manifest.json"
fi

echo "==> (Optional) Network reproduction of the corpus study and real-repo tests:"
echo "    TELEMETRY_CONTRACTS_NETWORK_TESTS=1 $PY -m telemetry_contracts.cli mine-corpus --manifest benchmarks/corpus/tier1.json --format markdown"
echo "    TELEMETRY_CONTRACTS_NETWORK_TESTS=1 $PY -m pytest tests/ -k real -o addopts=''"
