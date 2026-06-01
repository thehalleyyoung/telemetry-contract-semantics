# Execution proof: safe runtime evidence for generated instrumentation

The tool can produce **runtime evidence** that its own deterministically
generated instrumentation proposals actually work — that they compile, import,
and (for the stdlib `logging` variant) emit telemetry carrying the promised
field names. This turns "here is a suggested snippet" into "here is a suggested
snippet, and here is proof it runs and emits the signal it claims".

## Honesty boundary

This is an **isolated generated-instrumentation compile/load/emission proof**. It
is deliberately **not** the target repository's build or test suite, which is
intentionally never run in a shared environment. Concretely:

- The tool executes **only its own** generated `annotate(...)` snippet — never any
  code from the target repository.
- Executed events are labeled `source: executed-instrumentation` and are
  **evidence only**: they are never folded into scoring or the differential, so
  the deterministic diagnosability scores are unaffected.
- The execution-proof section carries `is_repository_finding: false` and no
  taxonomy codes; it sits beside `feature_scorecard` and `depth_summary` in the
  pipeline report (only when explicitly requested).

## What is proved, and how it stays safe

1. **Regenerate, never trust stored text.** Each snippet is regenerated from the
   trusted `(gap, library_kind)` fields and the trusted intended-field table —
   the proposal's stored `snippet` string is never executed. A tampered snippet
   in a proposal dict cannot influence the proof.
2. **Validate field names.** Every intended field name must be a valid
   identifier, not a Python keyword, and not collide with a reserved `LogRecord`
   attribute; otherwise the proposal is reported `not-executed-invalid-names`.
3. **AST allowlist.** The regenerated snippet is parsed and checked against a
   strict, exact-shape allowlist: only `logging` / `opentelemetry` imports, one
   module-level helper assignment, exactly one `annotate` function, and a small
   closed set of AST node types. Any forbidden name (`eval`, `exec`, `os`,
   `subprocess`, `socket`, …), dunder attribute access, extra function, class, or
   import fails validation and yields `not-executed-unsafe` — no execution.
4. **Hardened isolated subprocess.** Validated snippets run via
   `python -I -S -B -E` (isolated, no site, no bytecode, no environment), with a
   stripped environment, a fresh empty working directory, `stdin` redirected to
   `/dev/null`, `close_fds=True`, a wall-clock timeout, and POSIX `setrlimit`
   CPU/file-size caps. (Address-space limits are intentionally omitted to avoid
   platform-specific interpreter-startup flakiness.)
5. **Deterministic emission capture.** For the `logging` variant a private,
   non-propagating logger with a single capturing handler records the emitted
   `LogRecord`s; only the level, the formatted message, and the sorted set of
   promised field names that are present are serialized — no timestamps, pids, or
   paths — as canonical JSON.

## Status taxonomy

| Status | Meaning |
| --- | --- |
| `emission-clean` | logging variant imported and emitted records carrying the promised fields |
| `build-clean` | compiled and imported in the isolated subprocess (emission not asserted) |
| `needs-optional-dep` | optional dependency (e.g. the OpenTelemetry SDK) not importable under isolated python |
| `not-executed-unsafe` | the snippet failed AST allowlist validation and was refused |
| `not-executed-invalid-names` | an intended field name was unsafe (keyword / reserved / non-identifier) |
| `execution-timeout` / `execution-crashed` / `execution-unavailable` | subprocess/runtime failure, kept distinct from a safety refusal |

## Reproducing

```bash
python3 -m telemetry_contracts.cli execute-proposals --path /path/to/checkout
```

The proof is deterministic and is witnessed offline by `tests/test_execution.py`
and on real repositories by `tests/test_execution_real.py`.
