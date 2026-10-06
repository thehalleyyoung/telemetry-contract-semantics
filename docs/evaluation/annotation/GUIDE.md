# Second-annotator guide

Status: **not yet done.** This packet is ready for an independent human
annotator. No second-annotator labels exist yet, and the repository reports no
inter-rater agreement until they do.

## Why this is needed

All 112 gold labels in `benchmarks/ground_truth/curated.jsonl` were written by
one person, the tool's author, who also wrote the detectors. An earlier version
of the gold generator hard-coded 17 "second labels". The same author wrote
them, so they did not measure agreement, and they have been removed. The 60
RQ3 findings in `results/rq3/validation_labels.csv` were labelled by an LLM
(the agent that ran the study). Both label sets need an independent human
check.

## Who should annotate

The annotator should have operated or debugged a production service with
structured logs or traces, for example as an SRE, backend engineer, or
security reviewer. They must not have worked on this tool. Expected effort is
about 2 hours for the gold sheet and 1.5 hours for the RQ3 sheet.

## Materials

| File | Contents |
| --- | --- |
| `gold_blinded.jsonl` | 112 items: opaque id, bug class, its definition, the events. No label, rationale, or original id. |
| `gold_sheet.csv` | Fill `label_present_yes_no` (`yes`/`no`), `confidence_1to3`, and an optional `note`. |
| `rq3_blinded.jsonl` | 60 findings the tool reported on public repositories: bug class, definition, a link to the file at the pinned commit, source line, the tool's message, and the flagged event. |
| `rq3_sheet.csv` | Fill the three label columns described below. |
| `key.json` | Maps opaque ids back to originals. **Do not open it before finishing.** |

Regenerate the packet with `python3 scripts/make_annotation_packet.py`.

## Task A: gold items (`gold_sheet.csv`)

For each item, answer: **is the bug class genuinely present in these events?**
Judge the intended meaning of the definition. Do not try to guess what a field
matcher would do:

* **missing-correlation.** If any event is a failure, can it be joined to a
  request or trace from the event alone? A correlation id under an unusual
  field name counts as present. An id that appears only inside free text
  counts as present only if a responder could reliably extract it.
* **missing-error-evidence.** Does every failure event carry structured
  evidence of the cause (an error code, exception type, or status)? A cause
  given only in free text means evidence is absent.
* **missing-duration.** Does a span event lack any duration or latency
  measure?
* **sensitive-values.** Does any value contain a raw secret or PII, such as an
  email, a token, a password, or a card or phone number? Encoded secrets (for
  example base64) count.
* **unclassified-sensitive.** Is a tenant, customer, account, or user
  identifier, or another sensitive attribute, emitted without redaction,
  hashing, or a privacy classification?
* **unbounded-cardinality.** Would a metric label take an unbounded number of
  distinct values in production? Judge the label semantics as well as the
  sample size.

Write `yes` or `no`. Use `confidence_1to3` for how sure you are (1 = guess,
3 = certain), and use `note` for any ambiguity.

## Task B: RQ3 findings (`rq3_sheet.csv`)

Open the linked file at the pinned commit if the event alone is not enough.

* `matches_definition`: `yes`, `no`, or `borderline`. Does the flagged event
  meet the bug-class definition? Use `borderline` only when the definition
  itself does not settle the case, for example a `session_id` that may or may
  not identify a user.
* `artifact_kind`: what kind of file holds the event:
  * `runtime-log`: telemetry the project itself produced and committed.
  * `sample-telemetry`: synthetic or example telemetry shipped as demo data.
  * `test-fixture`: a test input.
  * `non-telemetry`: not telemetry at all, such as a dataset, an issue
    tracker, or model outputs.
* `actionable_in_project_telemetry`: `yes`, `no`, or `unclear`. Would a
  maintainer plausibly treat this as an observability or privacy defect in
  telemetry the project emits?

## After annotation

```bash
python3 scripts/annotation_agreement.py \
  --gold-sheet path/to/gold_sheet.csv --rq3-sheet path/to/rq3_sheet.csv \
  --out results/annotation_agreement.json
```

The script reports Cohen's kappa, a 95% bootstrap interval, and the
disagreements. For the gold set it also re-scores the tool on the items where
both raters agree. Resolve disagreements by discussion against the written
definitions, record the outcome in a new column, and report kappa computed
before adjudication. Commit the filled sheets unchanged, along with the
annotator's role and a statement that they did not see `key.json` or the
first-rater labels.
