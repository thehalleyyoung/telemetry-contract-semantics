"""Offline tests for the deterministic baseline comparison (Phase 4)."""

from __future__ import annotations

import json
import pathlib

import pytest

from telemetry_contracts.bug_classes import BUG_CLASS_IDS
from telemetry_contracts.evaluation.baselines import (
    build_llm_prompt,
    build_surrogate_cache,
    compare_baselines,
    llm_cache_key,
    make_recorded_surrogate_predictor,
    parse_llm_verdict,
    predict_rule_light,
    predict_semantic_convention_only,
    render_baselines_markdown,
    surrogate_verdict,
    _mcnemar_exact,
)
from telemetry_contracts.evaluation.ground_truth import load_gold_set

ROOT = pathlib.Path(__file__).resolve().parents[1]
GOLD = ROOT / "benchmarks" / "ground_truth" / "curated.jsonl"
CACHE = ROOT / "benchmarks" / "baselines" / "llm_recorded.json"


@pytest.fixture(scope="module")
def gold():
    return load_gold_set(str(GOLD))


@pytest.fixture(scope="module")
def cache():
    with open(CACHE, encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def comparison(gold, cache):
    return compare_baselines(gold, cache)


# --- predictor unit behaviour ----------------------------------------------


def test_rule_light_flags_only_field_names():
    # No correlation field name -> gap; has one -> no gap (ignores failure gating).
    assert predict_rule_light([{"name": "x"}], "missing-correlation")[0] is True
    assert predict_rule_light([{"trace_id": "t"}], "missing-correlation")[0] is False


def test_rule_light_is_value_blind_for_sensitive():
    # Raw secret in an innocently-named field is NOT caught by name-only rule-light.
    present, _ = predict_rule_light([{"blob": "AKIA1234567890SECRET"}], "sensitive-values")
    assert present is False
    # But a sensitive *name* is caught.
    assert predict_rule_light([{"password": "x"}], "sensitive-values")[0] is True


def test_rule_light_never_flags_cardinality():
    big = [{"session_id": str(i), "value": i} for i in range(200)]
    assert predict_rule_light(big, "unbounded-cardinality")[0] is False


def test_semantic_convention_only_out_of_scope_classes_always_negative():
    for gap in ("sensitive-values", "unclassified-sensitive", "unbounded-cardinality"):
        present, codes = predict_semantic_convention_only([{"password": "p"}], gap)
        assert present is False
        assert codes == []


def test_semantic_convention_uses_otel_trace_context_only():
    # request_id is NOT OTel trace context -> convention baseline still flags a gap.
    assert predict_semantic_convention_only([{"request_id": "r"}], "missing-correlation")[0] is True
    assert predict_semantic_convention_only([{"trace_id": "t"}], "missing-correlation")[0] is False


def test_baseline_witness_codes_are_namespaced():
    _, codes = predict_rule_light([{"name": "x"}], "missing-correlation")
    assert codes == ["baseline.rule_light.missing_correlation"]
    _, codes2 = predict_semantic_convention_only([{"name": "x"}], "missing-duration")
    assert codes2 == ["baseline.semantic_convention.missing_duration"]


# --- llm harness ------------------------------------------------------------


def test_llm_prompt_is_deterministic_and_carries_definition():
    events = [{"b": 2, "a": 1}]
    p1 = build_llm_prompt(events, "missing-correlation")
    p2 = build_llm_prompt([{"a": 1, "b": 2}], "missing-correlation")
    assert p1 == p2  # canonical JSON ordering
    assert "missing-correlation" in p1


def test_parse_llm_verdict_handles_yes_no_and_rejects_garbage():
    assert parse_llm_verdict("YES\nbecause ...") is True
    assert parse_llm_verdict("no, looks fine") is False
    with pytest.raises(ValueError):
        parse_llm_verdict("maybe")


def test_llm_cache_key_is_order_independent_over_event_keys():
    k1 = llm_cache_key([{"a": 1, "b": 2}], "missing-duration")
    k2 = llm_cache_key([{"b": 2, "a": 1}], "missing-duration")
    assert k1 == k2
    assert k1 != llm_cache_key([{"a": 1, "b": 2}], "missing-correlation")


def test_surrogate_overflags_on_failure_cue():
    present, rationale = surrogate_verdict(
        [{"trace_id": "t", "severity": "error", "error": "boom"}], "missing-correlation"
    )
    assert present is True
    assert "failure" in rationale


def test_recorded_surrogate_cache_round_trips(gold):
    cache = build_surrogate_cache(gold)
    predict = make_recorded_surrogate_predictor(cache)
    for item in gold:
        present, codes = predict(item.events, item.bug_class)
        assert isinstance(present, bool)
        if present:
            assert codes == [f"baseline.recorded_surrogate.{item.bug_class.replace('-', '_')}"]


def test_recorded_surrogate_cache_miss_raises(gold):
    predict = make_recorded_surrogate_predictor({"responses": {}})
    with pytest.raises(KeyError):
        predict(gold[0].events, gold[0].bug_class)


def test_shipped_cache_matches_regenerated(gold, cache):
    regenerated = build_surrogate_cache(gold)
    assert cache["responses"] == regenerated["responses"]


# --- mcnemar ----------------------------------------------------------------


def test_mcnemar_exact_known_values():
    # No discordance -> p == 1.0.
    assert _mcnemar_exact(0, 0)["two_sided_exact_p_ten_thousandths"] == 10000
    # b=20, c=1 is highly significant.
    m = _mcnemar_exact(20, 1)
    assert m["significant_at_0p05"] is True
    assert m["discordant_total"] == 21
    # b=c=1 -> p = 2 * (C(2,0)+C(2,1))/4 = 2*3/4 = 1.5 -> clamped to 1.0.
    assert _mcnemar_exact(1, 1)["two_sided_exact_p_ten_thousandths"] == 10000


# --- full comparison: structure, locks, determinism ------------------------


def test_comparison_has_all_methods_and_no_internal_leak(comparison):
    ids = [m["id"] for m in comparison["methods"]]
    assert ids == ["tool", "rule-light", "semantic-convention-only", "recorded-surrogate"]
    blob = json.dumps(comparison, sort_keys=True)
    assert '"_correct"' not in blob


def test_out_of_scope_classes_never_predicted_positive(gold, cache):
    comparison = compare_baselines(gold, cache)
    # For each method, items in its out-of-scope classes must contribute zero
    # predicted positives (tp+fp over those classes == 0).
    from telemetry_contracts.evaluation.baselines import (
        predict_rule_light as rl,
        predict_semantic_convention_only as sc,
    )

    for predict, oos in (
        (rl, ["unbounded-cardinality"]),
        (sc, ["sensitive-values", "unclassified-sensitive", "unbounded-cardinality"]),
    ):
        for item in gold:
            if item.bug_class in oos:
                assert predict(item.events, item.bug_class)[0] is False


def test_headline_numbers_are_locked(comparison):
    by_id = {m["id"]: m for m in comparison["methods"]}
    assert by_id["tool"]["overall"]["f1_permille"] == 953
    assert by_id["tool"]["overall"]["predicted_positive"] == 53
    assert by_id["rule-light"]["overall"]["f1_permille"] == 750
    assert by_id["semantic-convention-only"]["overall"]["f1_permille"] == 557
    assert by_id["recorded-surrogate"]["overall"]["f1_permille"] == 563
    # The tool beats every baseline with a significant paired McNemar test.
    for sid in ("rule-light", "semantic-convention-only", "recorded-surrogate"):
        mc = by_id[sid]["vs_tool"]["mcnemar"]
        assert mc["significant_at_0p05"] is True
        assert mc["discordant_tool_only"] > mc["discordant_baseline_only"]


def test_covered_class_view_is_not_worse_than_all_class_for_limited_baselines(comparison):
    by_id = {m["id"]: m for m in comparison["methods"]}
    sc = by_id["semantic-convention-only"]
    # Covered-class F1 should be >= all-class F1 because out-of-scope classes
    # only ever add false negatives / true negatives for this baseline.
    assert sc["covered"]["f1_permille"] >= sc["overall"]["f1_permille"]
    assert sorted(sc["out_of_scope_classes"]) == [
        "sensitive-values",
        "unbounded-cardinality",
        "unclassified-sensitive",
    ]


def test_comparison_is_byte_deterministic(gold, cache):
    a = json.dumps(compare_baselines(gold, cache), sort_keys=True)
    b = json.dumps(compare_baselines(gold, cache), sort_keys=True)
    assert a == b


def test_markdown_renders_all_sections(comparison):
    md = render_baselines_markdown(comparison)
    for heading in (
        "All-class (micro-averaged)",
        "Covered-class only",
        "Paired significance vs the tool",
        "Symmetric win/loss vs the tool",
        "Cost / feasibility",
    ):
        assert heading in md
    assert "NOT" not in comparison["methods"][0]["description"]  # tool isn't disclaimed


def test_all_bug_classes_present_in_per_class(comparison):
    for m in comparison["methods"]:
        assert sorted(m["per_class_f1_permille"]) == sorted(BUG_CLASS_IDS)
