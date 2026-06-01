#!/usr/bin/env bash
# Download every pinned corpus subject into a local, git-ignored directory.
#
# The corpus manifest (benchmarks/corpus/*.json) pins each subject repository to
# an exact commit SHA. This script clones each one at that SHA into
# benchmarks/corpus/_repos/ (git-ignored) so you can run the study locally
# without re-downloading. Re-running is idempotent: an existing checkout already
# at the right SHA is left untouched.
#
# Usage:
#   scripts/download_corpus.sh                         # download tier-1 (fast)
#   scripts/download_corpus.sh --manifest benchmarks/corpus/tier2.json
#   scripts/download_corpus.sh --tier 2                # all subjects up to tier 2
#   REPOS_DIR=/tmp/corpus scripts/download_corpus.sh   # custom destination
#
# After downloading, run the study incrementally (cached + resumable):
#   python3 -m telemetry_contracts.cli corpus-run \
#       --manifest benchmarks/corpus/tier2.json \
#       --repos-dir benchmarks/corpus/_repos \
#       --format markdown
set -euo pipefail

cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
MANIFEST="benchmarks/corpus/tier1.json"
REPOS_DIR="${REPOS_DIR:-benchmarks/corpus/_repos}"
TIER_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --manifest) MANIFEST="$2"; shift 2 ;;
    --tier) TIER_ARGS=(--tier "$2"); shift 2 ;;
    --repos-dir) REPOS_DIR="$2"; shift 2 ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

echo "==> Downloading corpus subjects from $MANIFEST into $REPOS_DIR"
"$PY" -m telemetry_contracts.cli corpus-download \
  --manifest "$MANIFEST" \
  --repos-dir "$REPOS_DIR" \
  ${TIER_ARGS[@]+"${TIER_ARGS[@]}"}

echo "==> Done. Checkouts are git-ignored under $REPOS_DIR"
