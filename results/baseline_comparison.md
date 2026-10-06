# Baseline comparison (head-to-head on the curated gold set)

All methods scored on the same **112** hand-labeled samples, through the identical pipeline. Metrics describe this curated, balanced set (not a prevalence-representative sample).

> Baseline definitions are fixed before snapshotting; no threshold is tuned on the gold set; every method sees only (events, bug_class), never the gold label or rationale. Out-of-scope classes are reported as coverage gaps, not accuracy failures.

## All-class (micro-averaged)

| Method | Kind | Precision | Recall | F1 | Macro F1 | Predicted+ | TP/FP/FN/TN |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| telemetry-contracts (this tool) | tool | 96.2% | 94.4% | 95.3% | 95.2% | 53 | 51/2/3/56 |
| rule-light keyword detector | baseline | 85.7% | 66.7% | 75.0% | 65.3% | 42 | 36/6/18/52 |
| OTel semantic-convention conformance | baseline | 62.8% | 50.0% | 55.7% | 39.6% | 43 | 27/16/27/42 |
| LLM zero-shot (anthropic/claude-haiku-4.5) | llm | 98.2% | 100.0% | 99.1% | 99.1% | 55 | 54/1/0/57 |
| LLM zero-shot (openai/gpt-4.1-mini) | llm | 98.0% | 92.6% | 95.2% | 95.0% | 51 | 50/1/4/57 |

## Covered-class only (excludes each method's out-of-scope classes)

| Method | Covered classes | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: |
| telemetry-contracts (this tool) | 6/6 | 96.2% | 94.4% | 95.3% |
| rule-light keyword detector | 5/6 | 85.7% | 76.6% | 80.9% |
| OTel semantic-convention conformance | 3/6 | 62.8% | 100.0% | 77.1% |
| LLM zero-shot (anthropic/claude-haiku-4.5) | 6/6 | 98.2% | 100.0% | 99.1% |
| LLM zero-shot (openai/gpt-4.1-mini) | 6/6 | 98.0% | 92.6% | 95.2% |

## Paired significance vs the tool (exact two-sided McNemar)

| Baseline | Tool-only correct | Baseline-only correct | Exact p | Sig. @0.05 |
| --- | ---: | ---: | ---: | :---: |
| rule-light keyword detector | 20 | 1 | 0.0000 | yes |
| OTel semantic-convention conformance | 38 | 0 | 0.0000 | yes |
| LLM zero-shot (anthropic/claude-haiku-4.5) | 0 | 4 | 0.1250 | no |
| LLM zero-shot (openai/gpt-4.1-mini) | 3 | 3 | 1.0000 | no |

## Symmetric win/loss vs the tool

### rule-light keyword detector

- Tool-only correct (20): `mc-neg-ok-00`, `mc-neg-ok-01`, `md-neg-evt-00`, `md-neg-evt-01`, `sv-pos-00`, `sv-pos-01`, `sv-pos-02`, `sv-pos-05`, `sv-pos-07`, `sv-pos-08`, `uc-pos-00`, `uc-pos-01`, `uc-pos-02`, `uc-pos-03`, `uc-pos-04`, `uc-pos-05`, `us-pos-03`, `us-pos-06`, `us-pos-07`, `us-pos-08`
- Baseline-only correct (1): `us-hard-altname`
- Shared false negatives (2): `sv-hard-b64`, `uc-hard-smallsample`
- Shared false positives (2): `mc-hard-altkey`, `me-hard-msgonly`

### OTel semantic-convention conformance

- Tool-only correct (38): `mc-neg-ok-00`, `mc-neg-ok-01`, `md-neg-evt-00`, `md-neg-evt-01`, `me-neg-00`, `me-neg-01`, `me-neg-02`, `me-neg-03`, `me-neg-04`, `me-neg-05`, `me-neg-06`, `me-neg-07`, `me-neg-08`, `me-neg-exc-00`, `sv-pos-00`, `sv-pos-01`, `sv-pos-02`, `sv-pos-03`, `sv-pos-04`, `sv-pos-05`, `sv-pos-06`, `sv-pos-07`, `sv-pos-08`, `uc-pos-00`, `uc-pos-01`, `uc-pos-02`, `uc-pos-03`, `uc-pos-04`, `uc-pos-05`, `us-pos-00`, `us-pos-01`, `us-pos-02`, `us-pos-03`, `us-pos-04`, `us-pos-05`, `us-pos-06`, `us-pos-07`, `us-pos-08`
- Baseline-only correct (0): —
- Shared false negatives (3): `sv-hard-b64`, `uc-hard-smallsample`, `us-hard-altname`
- Shared false positives (2): `mc-hard-altkey`, `me-hard-msgonly`

### LLM zero-shot (anthropic/claude-haiku-4.5)

- Tool-only correct (0): —
- Baseline-only correct (4): `mc-hard-altkey`, `sv-hard-b64`, `uc-hard-smallsample`, `us-hard-altname`
- Shared false negatives (0): —
- Shared false positives (1): `me-hard-msgonly`

### LLM zero-shot (openai/gpt-4.1-mini)

- Tool-only correct (3): `us-pos-05`, `us-pos-06`, `us-pos-07`
- Baseline-only correct (3): `mc-hard-altkey`, `sv-hard-b64`, `uc-hard-smallsample`
- Shared false negatives (1): `us-hard-altname`
- Shared false positives (1): `me-hard-msgonly`

## Cost / feasibility

| Method | Setup | Conventions | Deterministic | Offline | Value-aware | Statistical |
| --- | --- | --- | :---: | :---: | :---: | :---: |
| telemetry-contracts (this tool) | none (point at telemetry you already have) | none | yes | yes | yes | yes |
| rule-light keyword detector | none | none | yes | yes | no | no |
| OTel semantic-convention conformance | adopt OTel semantic conventions | OpenTelemetry | yes | yes | no | no |
| LLM zero-shot (anthropic/claude-haiku-4.5) | API key + per-item model call | none | no | no | yes | no |
| LLM zero-shot (openai/gpt-4.1-mini) | API key + per-item model call | none | no | no | yes | no |

