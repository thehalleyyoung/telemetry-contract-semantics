"""Snapshot and determinism tests for the observability badge and scorecard.

The badge SVG, scorecard SVG, and shields.io endpoint JSON must be byte-stable
across runs and inputs (no wall-clock, no RNG), produce well-formed XML, and pick
the correct color band per score. Snapshots lock the byte output for the headline
scores so a rendering change is caught immediately.
"""

from __future__ import annotations

import xml.dom.minidom as minidom

import pytest

from telemetry_contracts.scorecard import (
    render_badge_svg,
    render_scorecard_svg,
    score_color,
    shields_endpoint_json,
)

_SAMPLE_REPORT = {
    "diagnosability_score": 72,
    "verdict": "under-instrumented for incidents",
    "top_gaps": [
        {"code": "telemetry.correlation_missing", "count": 4, "severity": "warning"},
        {"code": "telemetry.duration_missing", "count": 2, "severity": "warning"},
    ],
}


@pytest.mark.parametrize(
    "score,expected",
    [
        (None, "#9f9f9f"),
        (0, "#e05d44"),
        (19, "#e05d44"),
        (20, "#fe7d37"),
        (40, "#dfb317"),
        (60, "#a4a61d"),
        (75, "#97ca00"),
        (89, "#97ca00"),
        (90, "#4c1"),
        (100, "#4c1"),
    ],
)
def test_color_bands(score, expected):
    assert score_color(score) == expected


def test_badge_is_well_formed_xml():
    for score in (None, 0, 50, 85, 100):
        svg = render_badge_svg(score)
        minidom.parseString(svg)  # raises on malformed XML
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")


def test_badge_is_byte_deterministic():
    assert render_badge_svg(85) == render_badge_svg(85)
    assert render_badge_svg(None) == render_badge_svg(None)


def test_badge_message_and_color_present():
    svg = render_badge_svg(85)
    assert "85/100" in svg
    assert score_color(85) in svg
    no_data = render_badge_svg(None)
    assert "no telemetry" in no_data
    assert "#9f9f9f" in no_data


def test_badge_snapshot_85():
    # Lock the byte output for the headline score so rendering regressions surface.
    assert render_badge_svg(85) == (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" width="134" height="20" '
        'role="img" aria-label="observability: 85/100">'
        '<title>observability: 85/100</title>'
        '<linearGradient id="s" x2="0" y2="100%">'
        '<stop offset="0" stop-color="#bbb" stop-opacity=".1"/>'
        '<stop offset="1" stop-opacity=".1"/></linearGradient>'
        '<clipPath id="r"><rect width="134" height="20" rx="3" fill="#fff"/></clipPath>'
        '<g clip-path="url(#r)">'
        '<rect width="88" height="20" fill="#555"/>'
        '<rect x="88" width="46" height="20" fill="#97ca00"/>'
        '<rect width="134" height="20" fill="url(#s)"/></g>'
        '<g fill="#fff" text-anchor="middle" '
        'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        'text-rendering="geometricPrecision" font-size="110">'
        '<text aria-hidden="true" x="440" y="150" fill="#010101" fill-opacity=".3" '
        'transform="scale(.1)" textLength="780">observability</text>'
        '<text x="440" y="140" transform="scale(.1)" '
        'textLength="780">observability</text>'
        '<text aria-hidden="true" x="1110" y="150" fill="#010101" fill-opacity=".3" '
        'transform="scale(.1)" textLength="360">85/100</text>'
        '<text x="1110" y="140" transform="scale(.1)" '
        'textLength="360">85/100</text>'
        '</g></svg>'
    )


def test_shields_endpoint_payload():
    payload = shields_endpoint_json(72)
    assert payload == {
        "schemaVersion": 1,
        "label": "observability",
        "message": "72/100",
        "color": "#a4a61d",
    }
    assert shields_endpoint_json(None)["message"] == "no telemetry"
    assert shields_endpoint_json(72) == shields_endpoint_json(72)


def test_custom_label():
    svg = render_badge_svg(90, label="o11y")
    assert "o11y" in svg
    assert shields_endpoint_json(90, label="o11y")["label"] == "o11y"


def test_scorecard_is_well_formed_and_deterministic():
    svg = render_scorecard_svg(_SAMPLE_REPORT)
    minidom.parseString(svg)
    assert svg == render_scorecard_svg(_SAMPLE_REPORT)
    assert "72" in svg
    assert "telemetry.correlation_missing" in svg
    assert "under-instrumented for incidents" in svg


def test_scorecard_no_telemetry_and_no_gaps():
    empty = {"diagnosability_score": None, "verdict": "no telemetry discovered", "top_gaps": []}
    svg = render_scorecard_svg(empty)
    minidom.parseString(svg)
    assert "no gaps detected" in svg
    perfect = {"diagnosability_score": 100, "verdict": "well-covered", "top_gaps": []}
    svg2 = render_scorecard_svg(perfect)
    minidom.parseString(svg2)
    assert "no gaps detected" in svg2


def test_scorecard_escapes_xml_special_chars():
    report = {
        "diagnosability_score": 50,
        "verdict": "a < b & c > d",
        "top_gaps": [{"code": "x<y&z", "count": 1, "severity": "warning"}],
    }
    svg = render_scorecard_svg(report)
    minidom.parseString(svg)  # would raise if special chars were not escaped
    assert "&lt;" in svg and "&amp;" in svg
