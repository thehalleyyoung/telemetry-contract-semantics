"""Deterministic, dependency-free SVG plots for the mining study (pure stdlib).

Two plots are produced directly from an aggregate dataset, with no plotting
library: a score-distribution histogram and a per-bug-class prevalence bar chart.
Both are byte-deterministic — fixed canvas geometry, integer coordinates only, a
fixed colour palette, stdlib XML escaping, sorted inputs, and no timestamps,
random ids, or floats — so they regenerate identically and can be diffed in CI.
"""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

from ..bug_classes import BUG_CLASS_IDS, BUG_CLASSES

# Canvas geometry (all integers).
_WIDTH = 720
_BAR_H = 24
_BAR_GAP = 8
_MARGIN_TOP = 56
_MARGIN_BOTTOM = 24
_LABEL_W = 220
_PLOT_W = 420
_AXIS_X = _LABEL_W + 8
_BAR_COLOR = "#2563eb"
_TRACK_COLOR = "#e5e7eb"
_TEXT_COLOR = "#111827"
_VALUE_COLOR = "#374151"
_FONT = "font-family='-apple-system,Segoe UI,Roboto,sans-serif'"


def _svg_header(width: int, height: int, title: str) -> list[str]:
    return [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' "
        f"viewBox='0 0 {width} {height}' role='img' aria-label='{escape(title)}'>",
        f"<rect x='0' y='0' width='{width}' height='{height}' fill='#ffffff'/>",
        f"<text x='16' y='28' {_FONT} font-size='18' font-weight='600' "
        f"fill='{_TEXT_COLOR}'>{escape(title)}</text>",
    ]


def _bar_row(y: int, label: str, value_text: str, filled: int) -> list[str]:
    filled = max(0, min(filled, _PLOT_W))
    return [
        f"<text x='16' y='{y + _BAR_H - 7}' {_FONT} font-size='13' "
        f"fill='{_TEXT_COLOR}'>{escape(label)}</text>",
        f"<rect x='{_AXIS_X}' y='{y}' width='{_PLOT_W}' height='{_BAR_H}' "
        f"rx='4' fill='{_TRACK_COLOR}'/>",
        f"<rect x='{_AXIS_X}' y='{y}' width='{filled}' height='{_BAR_H}' "
        f"rx='4' fill='{_BAR_COLOR}'/>",
        f"<text x='{_AXIS_X + _PLOT_W + 8}' y='{y + _BAR_H - 7}' {_FONT} "
        f"font-size='12' fill='{_VALUE_COLOR}'>{escape(value_text)}</text>",
    ]


def render_prevalence_svg(dataset: dict[str, Any]) -> str:
    """A horizontal bar chart of per-bug-class prevalence (permille of telemetry repos)."""

    prevalence = dataset.get("bug_class_prevalence", {})
    rows = [
        (BUG_CLASSES[gap]["title"], prevalence.get(gap, {}).get("subjects_present", 0),
         prevalence.get(gap, {}).get("subjects_present_permille", 0))
        for gap in BUG_CLASS_IDS
    ]
    n = len(rows)
    height = _MARGIN_TOP + n * (_BAR_H + _BAR_GAP) + _MARGIN_BOTTOM
    parts = _svg_header(_WIDTH, height, "Bug-class prevalence (share of telemetry-bearing repos)")
    y = _MARGIN_TOP
    for title, present, permille in rows:
        # Bar is scaled by permille against a full-width 1000-permille axis.
        filled = (permille * _PLOT_W) // 1000
        value_text = f"{present} ({permille // 10}.{permille % 10}%)"
        parts.extend(_bar_row(y, title, value_text, filled))
        y += _BAR_H + _BAR_GAP
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# Fixed score buckets (lower-inclusive, upper-inclusive) over the 0..100 score.
_SCORE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("0-19", 0, 19),
    ("20-39", 20, 39),
    ("40-59", 40, 59),
    ("60-79", 60, 79),
    ("80-100", 80, 100),
)


def _score_histogram(dataset: dict[str, Any]) -> list[tuple[str, int]]:
    counts = {label: 0 for label, _, _ in _SCORE_BUCKETS}
    for row in dataset.get("subjects", []):
        score = row.get("diagnosability_score")
        if score is None:
            continue
        score = int(score)
        for label, low, high in _SCORE_BUCKETS:
            if low <= score <= high:
                counts[label] += 1
                break
    return [(label, counts[label]) for label, _, _ in _SCORE_BUCKETS]


def render_score_histogram_svg(dataset: dict[str, Any]) -> str:
    """A histogram of diagnosability scores across telemetry-bearing subjects."""

    rows = _score_histogram(dataset)
    n = len(rows)
    max_count = max((c for _, c in rows), default=0)
    height = _MARGIN_TOP + n * (_BAR_H + _BAR_GAP) + _MARGIN_BOTTOM
    parts = _svg_header(_WIDTH, height, "Diagnosability score distribution")
    y = _MARGIN_TOP
    for label, count in rows:
        filled = 0 if max_count == 0 else (count * _PLOT_W) // max_count
        parts.extend(_bar_row(y, label, str(count), filled))
        y += _BAR_H + _BAR_GAP
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_plots(dataset: dict[str, Any]) -> dict[str, str]:
    """Return ``{filename: svg}`` for every study plot."""

    return {
        "score_distribution.svg": render_score_histogram_svg(dataset),
        "bug_class_prevalence.svg": render_prevalence_svg(dataset),
    }
