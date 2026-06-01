"""Ground-truth precision/recall evaluation for the observability bug classes.

This package turns the deterministic per-event detectors into a measurable
*accuracy* claim: given a hand-labeled gold set (one labeled sample per line),
it computes per-class and overall precision / recall / F1, a confusion matrix,
a representative error analysis, and an optional inter-rater agreement (Cohen's
kappa) — all with byte-stable arithmetic and no network or randomness.
"""

from __future__ import annotations

from .ground_truth import (
    GOLD_SCHEMA,
    GoldItem,
    GroundTruthError,
    load_gold_set,
    parse_gold_lines,
)
from .scorer import (
    EVAL_SCHEMA,
    predict_bug_class,
    render_evaluation_markdown,
    score_gold_set,
)
from .baselines import (
    BASELINES_SCHEMA,
    build_llm_prompt,
    build_surrogate_cache,
    compare_baselines,
    llm_cache_key,
    make_recorded_surrogate_predictor,
    parse_llm_verdict,
    predict_rule_light,
    predict_semantic_convention_only,
    render_baselines_markdown,
)

__all__ = [
    "GOLD_SCHEMA",
    "GoldItem",
    "GroundTruthError",
    "load_gold_set",
    "parse_gold_lines",
    "EVAL_SCHEMA",
    "predict_bug_class",
    "render_evaluation_markdown",
    "score_gold_set",
    "BASELINES_SCHEMA",
    "build_llm_prompt",
    "build_surrogate_cache",
    "compare_baselines",
    "llm_cache_key",
    "make_recorded_surrogate_predictor",
    "parse_llm_verdict",
    "predict_rule_light",
    "predict_semantic_convention_only",
    "render_baselines_markdown",
]
