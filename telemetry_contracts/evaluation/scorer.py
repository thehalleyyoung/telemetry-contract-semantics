"""Deterministic precision/recall scorer over a hand-labeled gold set.

Runs the same zero-config detectors the tool ships (``analyze_events`` for five
classes; ``diagnose`` component counts for missing-duration) over each gold
sample, compares the prediction to the gold label, and reports per-class and
overall precision / recall / F1, a confusion matrix, a representative error
analysis, and an optional Cohen's kappa. All arithmetic is integer / fixed-point
(per-mille, half-up) so the report is byte-identical across machines.
"""

from __future__ import annotations

from typing import Any, Callable

from ..bug_classes import BUG_CLASS_IDS, CODE_TO_BUG_CLASS
from ..discover import analyze_events
from ..pipeline import diagnose
from .ground_truth import GoldItem

EVAL_SCHEMA = "telemetry-contracts/gold-eval@1"

# A predictor maps (events, bug_class) -> (present, witness_codes). The shipped
# tool (``predict_bug_class``) is the default; baselines supply alternatives with
# the same signature so they can be scored through the identical pipeline.
Predictor = Callable[[list[dict[str, Any]], str], "tuple[bool, list[str]]"]

# Cap on how many representative errors of each kind we surface in the report.
_MAX_ERROR_EXAMPLES = 8


def predict_bug_class(events: list[dict[str, Any]], bug_class: str) -> tuple[bool, list[str]]:
    """Predict whether ``bug_class`` is present in ``events``.

    Returns ``(present, codes)`` where ``codes`` are the witnessing finding
    codes for that class (empty when absent). Uses the data detectors exactly as
    the shipped CLI would, so the benchmark measures the real tool.
    """

    if bug_class == "missing-duration":
        # missing-duration is accounted by the diagnosis component counts rather
        # than an analyze_events finding; mirror the engine's own logic.
        components = diagnose(events)["components"]
        present = int(components.get("spans_without_duration", 0)) > 0
        return present, (["telemetry.missing_field"] if present else [])

    codes = sorted(
        {
            str(f["code"])
            for f in analyze_events(events)["findings"]
            if CODE_TO_BUG_CLASS.get(str(f["code"])) == bug_class
        }
    )
    return bool(codes), codes


def _ratio_permille(numerator: int, denominator: int) -> int | None:
    """Half-up per-mille of ``numerator/denominator`` (``None`` when undefined)."""

    if denominator <= 0:
        return None
    return (numerator * 1000 + denominator // 2) // denominator


def _class_metrics(tp: int, fp: int, fn: int, tn: int) -> dict[str, Any]:
    precision = _ratio_permille(tp, tp + fp)
    recall = _ratio_permille(tp, tp + fn)
    f1 = _ratio_permille(2 * tp, 2 * tp + fp + fn)
    return {
        "support_positive": tp + fn,
        "support_negative": fp + tn,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision_permille": precision,
        "recall_permille": recall,
        "f1_permille": f1,
    }


def _cohen_kappa_permille(pairs: list[tuple[bool, bool]]) -> int | None:
    """Cohen's kappa (per-mille) over (label, second_label) binary pairs."""

    n = len(pairs)
    if n == 0:
        return None
    agree = sum(1 for a, b in pairs if a == b)
    po = agree / n
    a_true = sum(1 for a, _ in pairs if a) / n
    b_true = sum(1 for _, b in pairs if b) / n
    pe = a_true * b_true + (1 - a_true) * (1 - b_true)
    if pe >= 1.0:
        # Perfect expected agreement (degenerate); kappa is undefined -> report
        # full agreement when observed agreement is also perfect, else 0.
        return 1000 if po >= 1.0 else 0
    kappa = (po - pe) / (1 - pe)
    # Clamp to [-1, 1] then map to signed per-mille, half-up away from zero.
    kappa = max(-1.0, min(1.0, kappa))
    scaled = kappa * 1000
    return int(scaled + (0.5 if scaled >= 0 else -0.5))


def score_gold_set(
    items: list[GoldItem], predictor: Predictor | None = None
) -> dict[str, Any]:
    """Score a gold set and return the deterministic evaluation dataset.

    ``predictor`` defaults to the shipped tool detectors (:func:`predict_bug_class`);
    a baseline may pass an alternative with the same signature to be scored
    through the identical pipeline.
    """

    predict = predictor or predict_bug_class
    per_class_counts: dict[str, dict[str, int]] = {
        gap: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for gap in BUG_CLASS_IDS
    }
    false_positives: list[dict[str, Any]] = []
    false_negatives: list[dict[str, Any]] = []
    kappa_pairs: list[tuple[bool, bool]] = []

    for item in items:
        predicted, codes = predict(item.events, item.bug_class)
        bucket = per_class_counts[item.bug_class]
        if item.label and predicted:
            bucket["tp"] += 1
        elif item.label and not predicted:
            bucket["fn"] += 1
            false_negatives.append(_error_row(item, predicted, codes))
        elif not item.label and predicted:
            bucket["fp"] += 1
            false_positives.append(_error_row(item, predicted, codes))
        else:
            bucket["tn"] += 1
        if item.second_label is not None:
            kappa_pairs.append((item.label, item.second_label))

    per_class = {
        gap: _class_metrics(**per_class_counts[gap]) for gap in BUG_CLASS_IDS
    }

    tp = sum(c["tp"] for c in per_class_counts.values())
    fp = sum(c["fp"] for c in per_class_counts.values())
    fn = sum(c["fn"] for c in per_class_counts.values())
    tn = sum(c["tn"] for c in per_class_counts.values())
    overall = _class_metrics(tp, fp, fn, tn)
    overall["samples"] = len(items)

    macro_f1 = _macro_average([per_class[g]["f1_permille"] for g in BUG_CLASS_IDS])
    macro_precision = _macro_average([per_class[g]["precision_permille"] for g in BUG_CLASS_IDS])
    macro_recall = _macro_average([per_class[g]["recall_permille"] for g in BUG_CLASS_IDS])

    false_positives.sort(key=lambda r: r["id"])
    false_negatives.sort(key=lambda r: r["id"])

    return {
        "schema": EVAL_SCHEMA,
        "overall": overall,
        "macro": {
            "precision_permille": macro_precision,
            "recall_permille": macro_recall,
            "f1_permille": macro_f1,
        },
        "per_class": per_class,
        "confusion_matrix": {
            gap: {
                "tp": per_class_counts[gap]["tp"],
                "fp": per_class_counts[gap]["fp"],
                "fn": per_class_counts[gap]["fn"],
                "tn": per_class_counts[gap]["tn"],
            }
            for gap in BUG_CLASS_IDS
        },
        "error_analysis": {
            "false_positives": false_positives[:_MAX_ERROR_EXAMPLES],
            "false_negatives": false_negatives[:_MAX_ERROR_EXAMPLES],
            "false_positive_total": len(false_positives),
            "false_negative_total": len(false_negatives),
        },
        "inter_rater": {
            "second_labeled": len(kappa_pairs),
            "cohen_kappa_permille": _cohen_kappa_permille(kappa_pairs),
        },
    }


def _error_row(item: GoldItem, predicted: bool, codes: list[str]) -> dict[str, Any]:
    return {
        "id": item.id,
        "bug_class": item.bug_class,
        "gold": item.label,
        "predicted": predicted,
        "codes": codes,
        "rationale": item.rationale,
    }


def _macro_average(values: list[int | None]) -> int | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    total = sum(present)
    return (total + len(present) // 2) // len(present)


def _fmt_permille(value: int | None) -> str:
    if value is None:
        return "n/a"
    return f"{value / 10:.1f}%"


def render_evaluation_markdown(dataset: dict[str, Any]) -> str:
    overall = dataset["overall"]
    macro = dataset["macro"]
    lines = [
        "# Ground-truth precision/recall (curated conformance benchmark)",
        "",
        f"Scored **{overall['samples']}** hand-labeled samples across "
        f"{len(dataset['per_class'])} bug classes. Metrics describe this curated, "
        f"balanced set (not a prevalence-representative real-world sample).",
        "",
        "## Overall (micro-averaged)",
        "",
        f"- Precision **{_fmt_permille(overall['precision_permille'])}**, "
        f"Recall **{_fmt_permille(overall['recall_permille'])}**, "
        f"F1 **{_fmt_permille(overall['f1_permille'])}**",
        f"- Confusion: TP {overall['tp']}, FP {overall['fp']}, "
        f"FN {overall['fn']}, TN {overall['tn']}",
        f"- Macro-averaged F1 **{_fmt_permille(macro['f1_permille'])}**",
        "",
        "## Per bug class",
        "",
        "| Bug class | Support (+/-) | Precision | Recall | F1 | TP/FP/FN/TN |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for gap in sorted(dataset["per_class"]):
        m = dataset["per_class"][gap]
        lines.append(
            f"| {gap} | {m['support_positive']}/{m['support_negative']} | "
            f"{_fmt_permille(m['precision_permille'])} | "
            f"{_fmt_permille(m['recall_permille'])} | "
            f"{_fmt_permille(m['f1_permille'])} | "
            f"{m['tp']}/{m['fp']}/{m['fn']}/{m['tn']} |"
        )
    ir = dataset["inter_rater"]
    if ir["second_labeled"]:
        lines += [
            "",
            "## Inter-rater reliability",
            "",
            f"Cohen's kappa over {ir['second_labeled']} doubly-labeled samples: "
            f"**{_fmt_permille(ir['cohen_kappa_permille'])}** (per-mille of 1.0).",
        ]
    ea = dataset["error_analysis"]
    lines += [
        "",
        "## Error analysis",
        "",
        f"False positives: {ea['false_positive_total']}; "
        f"false negatives: {ea['false_negative_total']} "
        f"(showing up to {_MAX_ERROR_EXAMPLES} of each).",
    ]
    for kind, label in (("false_positives", "False positive"), ("false_negatives", "False negative")):
        for row in ea[kind]:
            lines.append(
                f"- **{label}** `{row['id']}` ({row['bug_class']}): {row['rationale']}"
            )
    return "\n".join(lines) + "\n"
