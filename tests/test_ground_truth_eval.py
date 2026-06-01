import json
from pathlib import Path

import pytest

from telemetry_contracts.evaluation import (
    GoldItem,
    GroundTruthError,
    load_gold_set,
    parse_gold_lines,
    predict_bug_class,
    render_evaluation_markdown,
    score_gold_set,
)

ROOT = Path(__file__).resolve().parents[1]
CURATED = ROOT / "benchmarks" / "ground_truth" / "curated.jsonl"


# --------------------------------------------------------------------------- #
# Gold-set schema / parser
# --------------------------------------------------------------------------- #
def test_parse_validates_and_sorts():
    text = "\n".join([
        json.dumps({"id": "b", "bug_class": "missing-duration", "label": True,
                    "events": [{"kind": "span", "name": "x"}], "rationale": "no duration"}),
        json.dumps({"id": "a", "bug_class": "missing-correlation", "label": False,
                    "events": [{"kind": "event", "name": "y", "trace_id": "t"}], "rationale": "has trace"}),
    ])
    items = parse_gold_lines(text)
    assert [it.id for it in items] == ["a", "b"]
    assert isinstance(items[0], GoldItem)


@pytest.mark.parametrize("bad,msg", [
    ({"id": "", "bug_class": "missing-duration", "label": True, "events": [{"kind": "span"}], "rationale": "r"}, "id"),
    ({"id": "x", "bug_class": "nope", "label": True, "events": [{"kind": "span"}], "rationale": "r"}, "bug_class"),
    ({"id": "x", "bug_class": "missing-duration", "label": "yes", "events": [{"kind": "span"}], "rationale": "r"}, "label"),
    ({"id": "x", "bug_class": "missing-duration", "label": True, "events": [], "rationale": "r"}, "events"),
    ({"id": "x", "bug_class": "missing-duration", "label": True, "events": [{"k": 1}], "rationale": ""}, "rationale"),
])
def test_parse_rejects_malformed(bad, msg):
    with pytest.raises(GroundTruthError) as exc:
        parse_gold_lines(json.dumps(bad))
    assert msg in str(exc.value)


def test_parse_rejects_duplicate_ids():
    line = json.dumps({"id": "dup", "bug_class": "missing-duration", "label": True,
                       "events": [{"kind": "span"}], "rationale": "r"})
    with pytest.raises(GroundTruthError):
        parse_gold_lines(line + "\n" + line)


# --------------------------------------------------------------------------- #
# Predictor behaviour per bug class
# --------------------------------------------------------------------------- #
def test_predict_missing_correlation():
    fail = [{"kind": "event", "name": "x", "severity": "error"}]
    ok = [{"kind": "event", "name": "x", "severity": "error", "trace_id": "t"}]
    assert predict_bug_class(fail, "missing-correlation")[0] is True
    assert predict_bug_class(ok, "missing-correlation")[0] is False


def test_predict_missing_duration_uses_diagnosis_components():
    span = [{"kind": "span", "name": "op"}]
    span_ok = [{"kind": "span", "name": "op", "duration_ms": 5}]
    assert predict_bug_class(span, "missing-duration")[0] is True
    assert predict_bug_class(span_ok, "missing-duration")[0] is False


def test_predict_unbounded_cardinality_needs_enough_distinct():
    pts = [{"kind": "metric", "name": "m", "user_id": f"u{i}", "value": 1} for i in range(60)]
    bounded = [{"kind": "metric", "name": "m", "status": ["a", "b"][i % 2], "value": 1} for i in range(60)]
    assert predict_bug_class(pts, "unbounded-cardinality")[0] is True
    assert predict_bug_class(bounded, "unbounded-cardinality")[0] is False


# --------------------------------------------------------------------------- #
# Scorer arithmetic
# --------------------------------------------------------------------------- #
def test_scorer_counts_and_metrics_on_tiny_set():
    items = [
        GoldItem("p1", "missing-correlation", True,
                 [{"kind": "event", "name": "x", "severity": "error"}], "no id"),       # TP
        GoldItem("p2", "missing-correlation", True,
                 [{"kind": "event", "name": "y", "severity": "error", "trace_id": "t"}], "mislabeled"),  # FN
        GoldItem("n1", "missing-correlation", False,
                 [{"kind": "event", "name": "z", "severity": "error", "trace_id": "t"}], "has id"),       # TN
        GoldItem("n2", "missing-correlation", False,
                 [{"kind": "event", "name": "w", "severity": "error"}], "mislabeled"),   # FP
    ]
    ds = score_gold_set(items)
    mc = ds["per_class"]["missing-correlation"]
    assert (mc["tp"], mc["fp"], mc["fn"], mc["tn"]) == (1, 1, 1, 1)
    assert mc["precision_permille"] == 500
    assert mc["recall_permille"] == 500
    assert mc["f1_permille"] == 500
    assert ds["overall"]["samples"] == 4
    assert ds["error_analysis"]["false_positive_total"] == 1
    assert ds["error_analysis"]["false_negative_total"] == 1


def test_scorer_is_deterministic():
    items = load_gold_set(CURATED)
    a = score_gold_set(items)
    b = score_gold_set(list(reversed(items)))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_cohen_kappa_on_known_pairs():
    # 10 pairs, 9 agree -> kappa computed deterministically and > 0.5.
    items = []
    for i in range(5):
        items.append(GoldItem(f"a{i}", "missing-duration", True,
                              [{"kind": "span", "name": "s"}], "r", second_label=True))
    for i in range(4):
        items.append(GoldItem(f"b{i}", "missing-duration", False,
                              [{"kind": "span", "name": "s", "duration_ms": 1}], "r", second_label=False))
    items.append(GoldItem("c0", "missing-duration", True,
                          [{"kind": "span", "name": "s"}], "r", second_label=False))  # disagreement
    ds = score_gold_set(items)
    assert ds["inter_rater"]["second_labeled"] == 10
    assert ds["inter_rater"]["cohen_kappa_permille"] > 500


# --------------------------------------------------------------------------- #
# Curated gold set: locked accuracy + quality bar
# --------------------------------------------------------------------------- #
def test_curated_gold_set_loads_and_is_balanced():
    items = load_gold_set(CURATED)
    assert len(items) >= 100
    classes = {it.bug_class for it in items}
    from telemetry_contracts.bug_classes import BUG_CLASS_IDS
    assert classes == set(BUG_CLASS_IDS)
    # every class has at least one positive and one negative
    for gap in BUG_CLASS_IDS:
        labels = {it.label for it in items if it.bug_class == gap}
        assert labels == {True, False}, gap


def test_curated_metrics_are_locked():
    ds = score_gold_set(load_gold_set(CURATED))
    assert ds["overall"]["samples"] == 112
    assert ds["overall"]["precision_permille"] == 962
    assert ds["overall"]["recall_permille"] == 944
    assert ds["overall"]["f1_permille"] == 953
    assert ds["macro"]["f1_permille"] == 952
    # Every residual error must be one of the documented hard cases (a subset
    # check, not exact equality, so a future detector improvement that fixes a
    # hard case strengthens — rather than breaks — the benchmark).
    known_fp = {"mc-hard-altkey", "me-hard-msgonly"}
    known_fn = {"sv-hard-b64", "uc-hard-smallsample", "us-hard-altname"}
    fp = {r["id"] for r in ds["error_analysis"]["false_positives"]}
    fn = {r["id"] for r in ds["error_analysis"]["false_negatives"]}
    assert fp <= known_fp, f"unexpected false positives: {fp - known_fp}"
    assert fn <= known_fn, f"unexpected false negatives: {fn - known_fn}"


def test_curated_meets_quality_bar():
    ds = score_gold_set(load_gold_set(CURATED))
    # Quality bar: overall and every per-class F1 stay above defensible floors,
    # so an accuracy regression fails this offline test.
    assert ds["overall"]["f1_permille"] >= 900
    for gap, m in ds["per_class"].items():
        assert m["f1_permille"] is not None and m["f1_permille"] >= 850, gap


def test_render_markdown_is_stable_and_complete():
    ds = score_gold_set(load_gold_set(CURATED))
    md = render_evaluation_markdown(ds)
    assert "Ground-truth precision/recall" in md
    assert "Per bug class" in md
    assert "Cohen's kappa" in md
    assert md == render_evaluation_markdown(ds)
