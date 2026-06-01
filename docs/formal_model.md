# Formal model: guarantees and executable witnesses

Each guarantee below is stated precisely, tied to the code that implements it and the test that witnesses it, and **discharged** by a deterministic executable check. The tool reports a machine-checkable verdict per obligation, so the paper can cite a checked count rather than a claim.

**13/13** obligations discharged (all hold) across 6 families: abstract-domains, assume-guarantee, monotonicity, preservation, refinement, termination.

> This document is generated. Regenerate it with
> `python3 -m telemetry_contracts.cli formal-model --format markdown` (guarantee
> sections) and `--format traceability` (the table at the end). The verdicts are
> deterministic; the witnesses live in `telemetry_contracts/formal_model.py` and
> are exercised by `tests/test_formal_model.py` (offline) and
> `tests/test_formal_model_real.py` (real repositories).

## abstract-domains

### `FM.abstract-domains.presence-soundness` ✓

The attribute-presence domain over-approximates presence: a field present in any event is never reported absent (sound for under-instrumentation claims).

- Approximation: **over-approximation**
- Implemented by: `abstract_domains:summarize_abstract_domains`
- Witnessed by: `tests/test_formal_model.py`, `tests/test_formal_model_real.py`
- Verdict: **holds** — present fields under-reported as absent: none

## assume-guarantee

### `FM.assume-guarantee.failing-flags` ✓

A violating finite trace produces a layer-specific counterexample (fail, at least one violated obligation).

- Approximation: **under-approximation**
- Implemented by: `assume_guarantee:evaluate_assume_guarantee`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — violating fixture: pass=False, violated=1

### `FM.assume-guarantee.passing-discharges` ✓

A satisfying finite trace discharges every declared layer obligation (pass, zero violations).

- Approximation: **under-approximation**
- Implemented by: `assume_guarantee:evaluate_assume_guarantee`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — satisfying fixture: pass=True, violated=0

## monotonicity

### `FM.monotonicity.nondecreasing` ✓

Applying a planned change never decreases diagnosability: the final score is at least the baseline and every applied round introduces zero regressions.

- Approximation: **exact**
- Implemented by: `pipeline:run_pipeline`
- Witnessed by: `tests/test_formal_model.py`, `tests/test_formal_model_real.py`
- Verdict: **holds** — baseline 85 ≤ final 100; applied rounds with 0 regressions=True

### `FM.monotonicity.regression-quarantined` ✓

A change whose differential would regress safety is quarantined and rolled back: it realizes zero score delta and applies zero changes.

- Approximation: **exact**
- Implemented by: `pipeline:run_pipeline`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — quarantined rounds=0, all with realized_delta=0 & 0 changes=True

## preservation

### `FM.preservation.benign-preserves` ✓

A transformation that retains the contract's witnesses preserves every runtime obligation (pass).

- Approximation: **exact**
- Implemented by: `preservation:check_transformation_preservation`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — identity/benign transform preserves obligations: pass=True

### `FM.preservation.destructive-detected` ✓

A transformation that destroys a required witness (e.g. over-redacting a correlation id) is detected as non-preserving (fail).

- Approximation: **exact**
- Implemented by: `preservation:check_transformation_preservation`
- Witnessed by: `tests/test_formal_model.py`, `tests/test_formal_model_real.py`
- Verdict: **holds** — destructive transform (drops trace_id) detected: pass=False

## refinement

### `FM.refinement.antisymmetry` ✓

Refinement is a partial order: mutually-refining contracts are equivalent, and a strict strengthening does not refine back (the order is non-trivial).

- Approximation: **exact**
- Implemented by: `refinement:check_contract_refinement`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — C⊑C′=True and C′⊑C=True; strict-strengthen refines-back=False

### `FM.refinement.order-soundness` ✓

The order is sound: a candidate that drops a required base obligation is rejected as a non-refinement (weakening is never accepted as refinement).

- Approximation: **over-approximation**
- Implemented by: `refinement:check_contract_refinement`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — weakening candidate (drops required trace_id) refines base = False

### `FM.refinement.reflexivity` ✓

Refinement is reflexive: every contract refines itself (C ⊑ C).

- Approximation: **exact**
- Implemented by: `refinement:check_contract_refinement`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — C ⊑ C refines=True

### `FM.refinement.transitivity` ✓

Refinement is transitive: if A ⊑ B and B ⊑ C then A ⊑ C, so a chain of strengthening edits composes into a single refinement of the original.

- Approximation: **exact**
- Implemented by: `refinement:check_contract_refinement`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — A⊑B=True, B⊑C=True, therefore A⊑C=True

## termination

### `FM.termination.bounded-rounds` ✓

The staged loop terminates within the configured round bound and always records a stopping reason.

- Approximation: **exact**
- Implemented by: `pipeline:run_pipeline`
- Witnessed by: `tests/test_formal_model.py`, `tests/test_formal_model_real.py`
- Verdict: **holds** — rounds=1 ≤ 2; stopped_reason='no further safety-approved high-impact changes'

### `FM.termination.monotonic-exclusion` ✓

The excluded/applied gap set grows monotonically: a gap planned in one round is never re-planned later, so the loop cannot cycle.

- Approximation: **exact**
- Implemented by: `pipeline:run_pipeline`
- Witnessed by: `tests/test_formal_model.py`
- Verdict: **holds** — distinct planned-gap sets across rounds (no re-planning) = True


# Formal-guarantee traceability (claim → code → test)

Every formal guarantee maps mechanically to the code that implements it, the test that witnesses it, and its discharge verdict.

| Guarantee id | Family | Approximation | Code | Tests | Discharged |
| --- | --- | --- | --- | --- | :---: |
| `FM.abstract-domains.presence-soundness` | abstract-domains | over-approximation | `abstract_domains:summarize_abstract_domains` | `tests/test_formal_model.py`<br>`tests/test_formal_model_real.py` | yes |
| `FM.assume-guarantee.failing-flags` | assume-guarantee | under-approximation | `assume_guarantee:evaluate_assume_guarantee` | `tests/test_formal_model.py` | yes |
| `FM.assume-guarantee.passing-discharges` | assume-guarantee | under-approximation | `assume_guarantee:evaluate_assume_guarantee` | `tests/test_formal_model.py` | yes |
| `FM.monotonicity.nondecreasing` | monotonicity | exact | `pipeline:run_pipeline` | `tests/test_formal_model.py`<br>`tests/test_formal_model_real.py` | yes |
| `FM.monotonicity.regression-quarantined` | monotonicity | exact | `pipeline:run_pipeline` | `tests/test_formal_model.py` | yes |
| `FM.preservation.benign-preserves` | preservation | exact | `preservation:check_transformation_preservation` | `tests/test_formal_model.py` | yes |
| `FM.preservation.destructive-detected` | preservation | exact | `preservation:check_transformation_preservation` | `tests/test_formal_model.py`<br>`tests/test_formal_model_real.py` | yes |
| `FM.refinement.antisymmetry` | refinement | exact | `refinement:check_contract_refinement` | `tests/test_formal_model.py` | yes |
| `FM.refinement.order-soundness` | refinement | over-approximation | `refinement:check_contract_refinement` | `tests/test_formal_model.py` | yes |
| `FM.refinement.reflexivity` | refinement | exact | `refinement:check_contract_refinement` | `tests/test_formal_model.py` | yes |
| `FM.refinement.transitivity` | refinement | exact | `refinement:check_contract_refinement` | `tests/test_formal_model.py` | yes |
| `FM.termination.bounded-rounds` | termination | exact | `pipeline:run_pipeline` | `tests/test_formal_model.py`<br>`tests/test_formal_model_real.py` | yes |
| `FM.termination.monotonic-exclusion` | termination | exact | `pipeline:run_pipeline` | `tests/test_formal_model.py` | yes |

