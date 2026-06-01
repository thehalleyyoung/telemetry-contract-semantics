"""Deterministic launch/demo asset rendering (terminal SVG, asciicast, social card).

These helpers turn a *captured* command transcript and a scan summary into
shareable assets for the README and launch posts. Everything is a pure function
of its inputs — fixed geometry, fixed asciicast timing, escaped text, no
wall-clock, no RNG — so the committed assets are byte-reproducible and can be
snapshot-tested.

We deliberately avoid third-party tools (svg-term, asciinema upload): the
terminal "GIF-like" demo is rendered as a self-contained SVG so it embeds
directly in the README and GitHub Pages with no external dependency.
"""

from __future__ import annotations

import json
from xml.sax.saxutils import escape

__all__ = [
    "render_terminal_svg",
    "build_asciicast",
    "render_social_card",
]

_MONO = "SFMono-Regular,Consolas,Liberation Mono,Menlo,monospace"


def _svg_lines(transcript: str) -> list[str]:
    # Normalize to a fixed-width window; keep determinism by not wrapping
    # (callers supply pre-wrapped transcripts).
    return transcript.replace("\r\n", "\n").rstrip("\n").split("\n")


def render_terminal_svg(transcript: str, *, title: str = "telemetry-contracts", cols: int = 86) -> str:
    """Render a captured terminal ``transcript`` as a self-contained SVG.

    Lines beginning with ``$ `` are styled as the prompt/command; other lines are
    program output. Geometry is fixed so the bytes are deterministic.
    """

    lines = _svg_lines(transcript)
    char_w = 7  # px per monospace column at 12px
    line_h = 18
    pad_x = 16
    pad_y = 14
    header_h = 28
    width = pad_x * 2 + cols * char_w
    height = header_h + pad_y * 2 + max(1, len(lines)) * line_h

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)} demo">'
    )
    out.append(f'<rect width="{width}" height="{height}" rx="8" fill="#0d1117"/>')
    out.append(f'<rect width="{width}" height="{header_h}" rx="8" fill="#161b22"/>')
    out.append(f'<rect y="{header_h - 8}" width="{width}" height="8" fill="#161b22"/>')
    for i, (cx, color) in enumerate([(18, "#f85149"), (36, "#d29922"), (54, "#3fb950")]):
        out.append(f'<circle cx="{cx}" cy="14" r="5" fill="{color}"/>')
    out.append(
        f'<text x="{width // 2}" y="18" fill="#8b949e" font-family="{_MONO}" '
        f'font-size="11" text-anchor="middle">{escape(title)}</text>'
    )
    out.append(f'<g font-family="{_MONO}" font-size="12">')
    y = header_h + pad_y + line_h - 5
    for line in lines:
        if line.startswith("$ "):
            out.append(f'<text x="{pad_x}" y="{y}" fill="#3fb950">$</text>')
            out.append(f'<text x="{pad_x + char_w * 2}" y="{y}" fill="#e6edf3">{escape(line[2:])}</text>')
        else:
            color = "#d29922" if line.strip().upper().startswith("WARNING") else "#8b949e"
            out.append(f'<text x="{pad_x}" y="{y}" fill="{color}">{escape(line)}</text>')
        y += line_h
    out.append("</g></svg>")
    return "".join(out)


def build_asciicast(transcript: str, *, title: str = "telemetry-contracts", width: int = 86, height: int | None = None) -> str:
    """Build a deterministic asciicast v2 (``.cast``) document from a transcript.

    Timing is fixed (one frame per line at a constant cadence) so the file is
    byte-reproducible; ``version``/header carry no timestamp.
    """

    lines = _svg_lines(transcript)
    rows = height if height is not None else max(1, len(lines)) + 2
    header = {"version": 2, "width": width, "height": rows, "title": title, "env": {"TERM": "xterm-256color"}}
    frames = []
    t = 0.0
    for line in lines:
        frames.append([round(t, 3), "o", line + "\r\n"])
        t += 0.6
    body = "\n".join(json.dumps(frame, separators=(",", ":")) for frame in frames)
    return json.dumps(header, separators=(",", ":"), sort_keys=True) + "\n" + body + "\n"


def _score_color(score: int | None) -> str:
    if score is None:
        return "#8b949e"
    if score >= 90:
        return "#3fb950"
    if score >= 75:
        return "#56b34a"
    if score >= 60:
        return "#a4a61d"
    if score >= 40:
        return "#d29922"
    if score >= 20:
        return "#db6d28"
    return "#f85149"


def render_social_card(
    *,
    title: str = "Observability is a correctness property",
    headline: str,
    score: int | None = None,
    score_label: str = "median score",
    footer: str = "telemetry-contracts",
) -> str:
    """Render a deterministic 1200x630 social/OpenGraph card reusing scorecard styling."""

    width, height = 1200, 630
    color = _score_color(score)
    score_text = "—" if score is None else str(score)

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
    )
    out.append(f'<rect width="{width}" height="{height}" fill="#0d1117"/>')
    out.append(f'<rect x="0" y="0" width="{width}" height="10" fill="#a371f7"/>')
    out.append(
        f'<text x="64" y="120" fill="#a371f7" font-family="{_MONO}" font-size="30">🔭 {escape(footer)}</text>'
    )
    # Title (caller must keep it to a single line that fits).
    out.append(
        f'<text x="64" y="230" fill="#e6edf3" font-family="-apple-system,Segoe UI,Roboto,sans-serif" '
        f'font-size="58" font-weight="700">{escape(title)}</text>'
    )
    out.append(
        f'<text x="64" y="320" fill="#8b949e" font-family="-apple-system,Segoe UI,Roboto,sans-serif" '
        f'font-size="34">{escape(headline)}</text>'
    )
    # Score dial.
    out.append(f'<circle cx="980" cy="450" r="120" fill="none" stroke="#30363d" stroke-width="16"/>')
    out.append(
        f'<text x="980" y="470" fill="{color}" font-family="{_MONO}" font-size="96" '
        f'font-weight="800" text-anchor="middle">{escape(score_text)}</text>'
    )
    out.append(
        f'<text x="980" y="610" fill="#8b949e" font-family="-apple-system,Segoe UI,Roboto,sans-serif" '
        f'font-size="28" text-anchor="middle">{escape(score_label)}</text>'
    )
    out.append("</svg>")
    return "".join(out)
