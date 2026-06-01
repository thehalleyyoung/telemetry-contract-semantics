# Artifact: Requirements

This document accompanies the artifact for **"Observability is a correctness
property"** and targets the ACM **Available** and **Reusable** badges.

## What the artifact is

A self-contained, pure-standard-library Python tool (`telemetry_contracts`) plus
its evaluation harness, frozen benchmark inputs, gold set, recorded baseline
cache, and a one-command reproduction that regenerates every offline figure,
table, and headline number and verifies them against a committed SHA-256
determinism manifest.

## Hardware requirements

None beyond a commodity machine. The offline reproduction runs in well under a
minute and needs no GPU, no special hardware, and no elevated privileges.

## Software requirements

- **Python ≥ 3.11** (uses `tomllib`; developed and tested through 3.12+).
- **git** on `PATH` (used for commit provenance and, only for the optional
  network reproduction, for cloning corpus repositories).
- **No third-party Python dependencies.** The runtime is standard library only.
  This is enforced by the test suite.
- Optional, only for the browser-playground smoke test: **Node.js ≥ 18** and the
  `pyodide` npm package.

## Network

- The **offline reproduction needs no network.** All evaluation inputs (the
  built-in benchmark, the curated gold set, and a transparent recorded-baseline
  cache) are committed and frozen.
- The **optional empirical reproduction** (the corpus study and the real-repo
  tests) clones pinned public repositories and therefore needs network access;
  it is gated behind `TELEMETRY_CONTRACTS_NETWORK_TESTS=1`.

## Determinism

Every artifact in the manifest is a pure function of the frozen inputs: no
wall-clock, no RNG, sorted aggregates, fixed-point arithmetic. The same inputs
produce byte-identical outputs across runs, hosts, and Python versions. Artifacts
that legitimately vary (measured runtime, absolute case-study paths, the git
commit hash) are explicitly excluded from the determinism manifest and documented
in `telemetry_contracts/reproduce.py`.

## Estimated time

- Offline reproduction (tests + manifest verification): **≈ 1 minute**.
- Optional network reproduction: a few minutes, dominated by shallow clones.
