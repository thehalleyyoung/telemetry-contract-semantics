# The high-impact filter

Every *addition* this tool proposes for a target repository — and every
capability the tool itself ships — is justified by a single, written rubric:

> **impact = analytic signal gained ÷ added surface area**

The rubric is deliberately mechanical so the same inputs always produce the same
score on any machine. It is a *decision aid*, not an automatic gate: the score is
always reported next to its breakdown so a human can judge it in context.

## Inputs (all mechanically derived)

| Term | Meaning | Where it comes from |
| --- | --- | --- |
| `questions_unblocked` | Incident questions a change makes answerable | the diagnosis' `unanswered_questions` linked to the change's gap |
| `signals_introduced` | Runtime field/attribute names the change adds | the static-checker–confirmed `present_in_source` names |
| `edges_introduced` | Ordering/correlation edges the change adds | one per correlation name introduced (conservative proxy) |
| `lines_added` | Source lines the change adds | the companion patch's added lines |
| `files_touched` | Distinct files the change adds/edits | the companion patch (a single new file) |

`analytic_signal = questions_unblocked + signals_introduced + edges_introduced`
and `surface_area = lines_added + files_touched`. The score is fixed-point:

```
impact_milli = 1000 * analytic_signal // surface_area      (integer division)
```

Zero surface area yields an explicit `indeterminate-zero-surface` verdict rather
than a division error. Verdict bands: `high-impact` (≥ 250), `moderate-impact`
(≥ 100), `low-impact` otherwise.

## Where it shows up

- **Per proposed change.** Every generated code proposal carries an
  `impact_score` with the verdict and full breakdown, so the highest-leverage
  instrumentation is obvious before anything is applied.
- **After the fact.** The staged pipeline emits a `feature_scorecard` that
  re-scores the *applied* changes of a real run (predicted vs. realized
  diagnosability gain per unit of surface area) and recommends `keep`, `prune`,
  or `merge`. When a single round applied several changes, their realized gains
  cannot be isolated, so attribution is honestly marked `confounded`. This
  scorecard is tool-maintenance metadata about the run — it is **not** a finding
  about the analyzed repository and emits no taxonomy codes.

## Worked example

```python
from telemetry_contracts import score_addition

score_addition(
    questions_unblocked=2,   # unblocks "which request failed?" + "what was the error?"
    signals_introduced=1,    # adds trace_id
    edges_introduced=1,      # correlates the failing signal
    lines_added=6,
    files_touched=1,
)
# -> impact_milli = (2 + 1 + 1) * 1000 // (6 + 1) = 571  -> "high-impact"
```

A change that touches 200 lines across 5 files to unblock a single question
scores `1000 // 205 = 4` → `low-impact`, which is exactly the signal the rubric
is meant to surface: cost must be earned by analytic yield.
