# Artifact: Status

We are applying for the following ACM badges.

## Artifacts Available

The artifact is publicly archived in a version-controlled public repository with
a stable history. All inputs required to reproduce the paper's offline results —
source, benchmark, gold set, recorded baseline cache, and the determinism
manifest — are included in the repository.

## Artifacts Evaluated — Reusable

We believe the artifact exceeds the bar for *Functional* and meets *Reusable*:

- **Documented.** Every public command is documented under `docs/`, the
  evaluation methodology under `docs/evaluation/`, and the threats to validity in
  `docs/evaluation/threats_to_validity.md`.
- **Consistent.** The artifact produces the paper's numbers: a single command
  regenerates all offline figures, tables, and headline statistics and verifies
  them, byte for byte, against a committed SHA-256 manifest.
- **Complete.** The tool, its evaluation harness, all three baselines, the
  formal-model witnesses, and the corpus-study driver are included.
- **Exercisable.** A comprehensive offline test suite runs without network in
  under a minute; an opt-in network suite reproduces the empirical corpus results
  against pinned public repositories.
- **Reusable.** The tool is a general-purpose, pure-stdlib library and CLI with a
  stable public API and a clean extension surface (adapters, baselines,
  formal-model guarantees). It runs on *any* repository, in CI, as a GitHub
  Action, and in the browser, not only on our benchmark.

## One-command reproduction

```bash
docs/artifact_evaluation/reproduce.sh --check
```

This runs the offline test suite and verifies every committed artifact against
the determinism manifest. A non-zero exit indicates drift.

## Provenance

The determinism manifest (`reports/reproduce_manifest.json`) records a SHA-256 for
each portable artifact. The CI `determinism` workflow runs the same `--check` on
every push, so any divergence between the committed artifacts and their
regenerated form fails the build.
