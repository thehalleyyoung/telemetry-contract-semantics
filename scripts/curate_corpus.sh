#!/usr/bin/env bash
# Curate a frozen corpus of real, telemetry-bearing repositories from live search.
#
# This is the reproducible path used to GROW the corpus. It (1) discovers
# candidate repositories that *commit* telemetry-shaped files via GitHub code
# search, then (2) clones each candidate into a git-ignored work directory, pins
# it to its exact current HEAD commit SHA, scans it, and keeps only those that
# genuinely ship parseable telemetry. The result is a pinned, verified corpus
# manifest (telemetry-contracts/corpus@1) you can commit as a new tier.
#
# Honesty: every SHA written is a real commit read from an actual checkout — no
# SHA is ever fabricated. The cloned repositories live under a git-ignored
# directory and are never committed; only the small JSON manifest is.
#
# Requirements: git, python3, and (for discovery) the `gh` CLI authenticated, or
# a GITHUB_TOKEN/GH_TOKEN in the environment.
#
# Usage:
#   scripts/curate_corpus.sh --output benchmarks/corpus/tier3.json --limit 50
#   scripts/curate_corpus.sh --candidates my_candidates.json \
#       --output benchmarks/corpus/tier3.json
#
# Options:
#   --output PATH        where to write the verified manifest (required)
#   --candidates PATH    reuse an existing candidates JSON instead of searching
#   --work-dir PATH      git-ignored clone directory (default: benchmarks/corpus/_curate)
#   --tier N             tier to assign to kept subjects (default: 2)
#   --limit N            stop after keeping N subjects (default: 50)
#   --allow-no-telemetry keep verified repos even if they ship no telemetry
set -euo pipefail

cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"
OUTPUT=""
CANDIDATES=""
WORK_DIR="benchmarks/corpus/_curate"
TIER="2"
LIMIT="50"
ALLOW_NO_TELEMETRY=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --output) OUTPUT="$2"; shift 2 ;;
    --candidates) CANDIDATES="$2"; shift 2 ;;
    --work-dir) WORK_DIR="$2"; shift 2 ;;
    --tier) TIER="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    --allow-no-telemetry) ALLOW_NO_TELEMETRY="--allow-no-telemetry"; shift ;;
    -h|--help) sed -n '2,33p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$OUTPUT" ]; then
  echo "ERROR: --output is required" >&2
  exit 2
fi

# Make a GitHub token available to the stdlib discovery helper if `gh` is present.
if [ -z "${GITHUB_TOKEN:-}" ] && [ -z "${GH_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
  GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"
  export GITHUB_TOKEN
fi

# Step 1: discover candidates (telemetry-bearing repos) unless a list was given.
if [ -z "$CANDIDATES" ]; then
  CANDIDATES="corpus_candidates.json"
  echo "Discovering telemetry-bearing candidates via code search -> $CANDIDATES" >&2
  "$PY" - "$CANDIDATES" <<'PYCODE'
import json, os, sys
from telemetry_contracts.mining.discover import search_github_code

token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
queries = [
    '"span_id" "trace_id" extension:jsonl',
    '"trace_id" "level" extension:jsonl',
    'path:logs extension:jsonl "message"',
    '"timestamp" "level" "service" extension:jsonl',
]
seen, candidates = set(), []
for q in queries:
    for c in search_github_code(query=q, limit=100, token=token):
        if c["target"] in seen:
            continue
        seen.add(c["target"])
        candidates.append({"target": c["target"]})
json.dump({"candidates": sorted(candidates, key=lambda c: c["target"])},
          open(sys.argv[1], "w"), indent=2)
print(f"  wrote {len(candidates)} candidates", file=sys.stderr)
PYCODE
fi

# Step 2: clone, pin, verify telemetry, and write the manifest.
echo "Curating verified subjects -> $OUTPUT" >&2
exec "$PY" -m telemetry_contracts.cli corpus-curate \
  --candidates "$CANDIDATES" \
  --work-dir "$WORK_DIR" \
  --output "$OUTPUT" \
  --tier "$TIER" \
  --limit "$LIMIT" \
  ${ALLOW_NO_TELEMETRY}
