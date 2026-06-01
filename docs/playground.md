# Zero-install browser playground

A static, dependency-free web playground that runs the **pure-stdlib** engine
**entirely in your browser** via [Pyodide](https://pyodide.org) — no backend, no
upload, nothing you paste ever leaves your machine. It is deployable as-is on
GitHub Pages (it is just static files under `playground/`).

## The 10-second flow

1. Open the page.
2. Click an example dataset (or paste your own logs/traces/metrics).
3. See your **diagnosability score**, the questions you can't answer yet, and the
   top under-instrumentation gaps — instantly, client-side.

The engine auto-detects whatever format you already have: JSON lines, a single
JSON array, logfmt (`key=value`), or an OTLP JSON export.

## How it works

`playground/build.py` assembles a byte-deterministic bundle into
`playground/assets/`:

- `telemetry_contracts.zip` — the package source, unpacked into Pyodide's
  in-memory filesystem at load time (`pyodide.unpackArchive`).
- `examples/` + `examples.json` — one-click example datasets (existing repository
  fixtures), so a first-time visitor sees real findings without typing anything.

`playground/app.js` boots Pyodide, loads the bundle, and calls a single shared,
tested entrypoint — `telemetry_contracts.playground.analyze_text(text)` — which
returns a compact JSON report (score, verdict, gaps, unanswered questions,
findings). That entrypoint is the *same* code path the CLI uses, so the browser
result matches the command line.

## Shareable results (no server)

The current input and service are encoded into the URL hash (base64-encoded
JSON). Copy the share link and anyone who opens it sees the same input
pre-loaded and analyzed — useful for posting a compelling result to social/HN/
Reddit without hosting anything.

## Running locally

```bash
python3 playground/build.py          # (re)build the bundle
cd playground && python3 -m http.server   # then open http://localhost:8000
```

## Keeping it from rotting

Because the engine is pure stdlib, it runs unmodified under Pyodide. A CI job
(`.github/workflows/playground-smoke.yml`) rebuilds the bundle, fails if the
committed bundle is stale, and runs `playground/smoke_test.mjs`, which loads the
engine under Pyodide in Node and asserts it imports and analyzes a known sample
deterministically. `analyze_text` itself is covered by offline snapshot/
determinism tests plus a network-gated test that runs it on telemetry from ≥4
real repositories.
