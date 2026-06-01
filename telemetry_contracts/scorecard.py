"""Deterministic observability badge and scorecard rendering.

Turns a diagnosability score (and optional gap summary) into:

* a shields-style flat **SVG badge** (``observability: NN/100``) with color bands;
* a one-image **scorecard SVG** (score + per-class gap summary) for embedding at
  the top of a README;
* a **shields.io-compatible JSON endpoint** so a live badge can be rendered
  without committing an image.

All outputs are pure-stdlib string templating and byte-deterministic: the same
inputs always produce identical bytes (no wall-clock, no RNG, fixed-point
geometry).
"""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

BADGE_LABEL = "observability"

# Color bands (shields.io palette). Ordered high -> low.
_COLOR_BANDS = (
    (90, "#4c1"),       # brightgreen
    (75, "#97ca00"),    # green
    (60, "#a4a61d"),    # yellowgreen
    (40, "#dfb317"),    # yellow
    (20, "#fe7d37"),    # orange
    (0, "#e05d44"),     # red
)
_NO_DATA_COLOR = "#9f9f9f"  # grey


def score_color(score: int | None) -> str:
    """Return the badge color for a score (grey when no telemetry)."""

    if score is None:
        return _NO_DATA_COLOR
    for floor, color in _COLOR_BANDS:
        if score >= floor:
            return color
    return _COLOR_BANDS[-1][1]


def _text_width(text: str) -> int:
    """Deterministic, font-metric-free text width estimate (px)."""

    return 6 * len(text) + 10


def _badge_message(score: int | None) -> str:
    return "no telemetry" if score is None else f"{score}/100"


def render_badge_svg(score: int | None, *, label: str = BADGE_LABEL) -> str:
    """Render a shields-style flat SVG badge. Deterministic for a given score."""

    message = _badge_message(score)
    color = score_color(score)
    label_w = _text_width(label)
    msg_w = _text_width(message)
    total_w = label_w + msg_w
    label_x = label_w * 10 // 2
    msg_x = (label_w * 10) + (msg_w * 10 // 2)
    label_e = escape(label)
    msg_e = escape(message)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" width="{total_w}" height="20" '
        f'role="img" aria-label="{label_e}: {msg_e}">'
        f'<title>{label_e}: {msg_e}</title>'
        f'<linearGradient id="s" x2="0" y2="100%">'
        f'<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        f'<stop offset="1" stop-opacity=".1"/></linearGradient>'
        f'<clipPath id="r"><rect width="{total_w}" height="20" rx="3" fill="#fff"/></clipPath>'
        f'<g clip-path="url(#r)">'
        f'<rect width="{label_w}" height="20" fill="#555"/>'
        f'<rect x="{label_w}" width="{msg_w}" height="20" fill="{color}"/>'
        f'<rect width="{total_w}" height="20" fill="url(#s)"/></g>'
        f'<g fill="#fff" text-anchor="middle" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'text-rendering="geometricPrecision" font-size="110">'
        f'<text aria-hidden="true" x="{label_x}" y="150" fill="#010101" fill-opacity=".3" '
        f'transform="scale(.1)" textLength="{(label_w - 10) * 10}">{label_e}</text>'
        f'<text x="{label_x}" y="140" transform="scale(.1)" '
        f'textLength="{(label_w - 10) * 10}">{label_e}</text>'
        f'<text aria-hidden="true" x="{msg_x}" y="150" fill="#010101" fill-opacity=".3" '
        f'transform="scale(.1)" textLength="{(msg_w - 10) * 10}">{msg_e}</text>'
        f'<text x="{msg_x}" y="140" transform="scale(.1)" '
        f'textLength="{(msg_w - 10) * 10}">{msg_e}</text>'
        f'</g></svg>'
    )


def shields_endpoint_json(score: int | None, *, label: str = BADGE_LABEL) -> dict[str, Any]:
    """Return a shields.io-compatible endpoint payload (schemaVersion 1)."""

    return {
        "schemaVersion": 1,
        "label": label,
        "message": _badge_message(score),
        "color": score_color(score),
    }


def _gap_rows(report: dict[str, Any], limit: int) -> list[tuple[str, int]]:
    gaps = report.get("top_gaps", [])
    return [(g["code"], g["count"]) for g in gaps[:limit]]


def render_scorecard_svg(report: dict[str, Any], *, max_gaps: int = 5) -> str:
    """Render a one-image scorecard SVG (score + per-class gap summary)."""

    score = report.get("diagnosability_score")
    color = score_color(score)
    verdict = escape(str(report.get("verdict", "")))
    rows = _gap_rows(report, max_gaps)
    width = 420
    header_h = 96
    row_h = 22
    height = header_h + 24 + max(len(rows), 1) * row_h + 16
    score_text = "—" if score is None else str(score)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'role="img" aria-label="Observability Report Card">',
        f'<rect width="{width}" height="{height}" rx="8" fill="#0d1117"/>',
        f'<rect x="0" y="0" width="{width}" height="{header_h}" rx="8" fill="#161b22"/>',
        f'<text x="20" y="34" fill="#c9d1d9" font-family="Verdana,DejaVu Sans,sans-serif" '
        f'font-size="16" font-weight="bold">Observability Report Card</text>',
        f'<text x="20" y="78" fill="{color}" font-family="Verdana,DejaVu Sans,sans-serif" '
        f'font-size="40" font-weight="bold">{score_text}<tspan font-size="18" fill="#8b949e">/100</tspan></text>',
        f'<text x="200" y="70" fill="#8b949e" font-family="Verdana,DejaVu Sans,sans-serif" '
        f'font-size="13">{verdict}</text>',
        f'<text x="20" y="{header_h + 20}" fill="#8b949e" '
        f'font-family="Verdana,DejaVu Sans,sans-serif" font-size="12">Top gaps</text>',
    ]
    y = header_h + 20 + row_h
    if rows:
        for code, count in rows:
            parts.append(
                f'<text x="28" y="{y}" fill="#c9d1d9" '
                f'font-family="DejaVu Sans Mono,monospace" font-size="12">{escape(code)}</text>'
            )
            parts.append(
                f'<text x="{width - 24}" y="{y}" fill="#f0883e" text-anchor="end" '
                f'font-family="Verdana,DejaVu Sans,sans-serif" font-size="12">{count}</text>'
            )
            y += row_h
    else:
        parts.append(
            f'<text x="28" y="{y}" fill="#3fb950" '
            f'font-family="Verdana,DejaVu Sans,sans-serif" font-size="12">no gaps detected</text>'
        )
    parts.append("</svg>")
    return "".join(parts)
