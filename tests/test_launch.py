"""Determinism + validity tests for launch/demo asset rendering.

The terminal SVG, asciicast, and social card are committed launch assets, so they
must be byte-reproducible and well-formed. We also assert the committed assets
under ``docs/launch/`` are in sync with the build script (no drift).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import xml.dom.minidom as minidom
from pathlib import Path

from telemetry_contracts.launch import build_asciicast, render_social_card, render_terminal_svg

_ROOT = Path(__file__).resolve().parents[1]
_LAUNCH = _ROOT / "docs" / "launch"

_SAMPLE = "$ telemetry-contracts scan-repo --repo o/r\nScanned: 4 finding(s).\n  WARNING telemetry.correlation_missing\n"


def test_terminal_svg_is_well_formed_and_deterministic():
    svg = render_terminal_svg(_SAMPLE)
    minidom.parseString(svg)
    assert svg == render_terminal_svg(_SAMPLE)
    assert svg.startswith("<svg") and svg.endswith("</svg>")


def test_terminal_svg_escapes_special_chars():
    svg = render_terminal_svg("$ echo '<a> & <b>'\nout: x < y & z\n")
    minidom.parseString(svg)
    assert "&lt;" in svg and "&amp;" in svg


def test_asciicast_is_valid_v2_and_deterministic():
    cast = build_asciicast(_SAMPLE)
    assert cast == build_asciicast(_SAMPLE)
    lines = cast.strip().split("\n")
    header = json.loads(lines[0])
    assert header["version"] == 2
    for frame in lines[1:]:
        rec = json.loads(frame)
        assert isinstance(rec[0], (int, float)) and rec[1] == "o"


def test_social_card_is_well_formed_and_deterministic():
    card = render_social_card(headline="half can't answer why a request failed", score=99)
    minidom.parseString(card)
    assert card == render_social_card(headline="half can't answer why a request failed", score=99)
    assert 'width="1200"' in card and 'height="630"' in card


def test_social_card_handles_no_score():
    card = render_social_card(headline="no telemetry", score=None)
    minidom.parseString(card)
    assert "#8b949e" in card


def _load_build():
    spec = importlib.util.spec_from_file_location("launch_build", _LAUNCH / "build.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["launch_build"] = module
    spec.loader.exec_module(module)
    return module


def test_committed_launch_assets_are_in_sync():
    before = {p.name: p.read_text(encoding="utf-8") for p in _LAUNCH.glob("*") if p.suffix in {".svg", ".cast", ".txt"}}
    build = _load_build()
    build.build()
    after = {p.name: p.read_text(encoding="utf-8") for p in _LAUNCH.glob("*") if p.suffix in {".svg", ".cast", ".txt"}}
    assert before == after, "docs/launch assets are stale; run 'python3 docs/launch/build.py' and commit"
