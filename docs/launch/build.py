#!/usr/bin/env python3
"""Build deterministic launch/demo assets under ``docs/launch/``.

Renders a captured, real ``scan-repo`` transcript (run against the public
repository ``almbayedahmad/medflux`` — authored without this tool in mind) into a
self-contained terminal SVG and an asciicast ``.cast``, plus a social/OpenGraph
card built from the frozen corpus headline statistic. All outputs are
byte-deterministic (no wall-clock, no RNG) and committed, so the README and
launch posts render with no external dependency. Pure stdlib; no network.

The transcript below is *real captured output*; re-running the command (with
network) reproduces it. The corpus numbers come from the frozen tier-1 study
(``benchmarks/corpus/tier1.json``); see ``docs/evaluation/corpus_study.md``.
"""

from __future__ import annotations

from pathlib import Path

from telemetry_contracts.launch import (
    build_asciicast,
    render_social_card,
    render_terminal_svg,
)

_OUT = Path(__file__).resolve().parent

# Real captured output of:
#   telemetry-contracts scan-repo --repo almbayedahmad/medflux --format text
_DEMO_TRANSCRIPT = """\
$ telemetry-contracts scan-repo --repo almbayedahmad/medflux
Scanned https://github.com/almbayedahmad/medflux.git: 5 telemetry file(s), 61 event(s), 4 finding(s) (0 error, 4 warning).

Top issue types:
  warning telemetry.correlation_missing     2
  warning telemetry.sensitive_unclassified  2

Findings (most severe first):
  WARNING telemetry.correlation_missing in logs/current.jsonl at event[1]:
          log 'medflux.uncaught' reports a failure but carries no correlation id
  WARNING telemetry.sensitive_unclassified at event[1].tenantID:
          field 'tenantID' is emitted without redaction/hashing or a classification

Next steps:
  - Understand a finding:  telemetry-contracts explain telemetry.correlation_missing
  - Lock it in:            telemetry-contracts infer-contract --events logs/current.jsonl
"""

# Frozen tier-1 corpus headline (reproduce: see docs/launch/blog_post.md).
_HEADLINE = "We scanned real repos; half of the failure-bearing ones can't say which request failed."


def build() -> dict[str, str]:
    demo_svg = render_terminal_svg(_DEMO_TRANSCRIPT, title="telemetry-contracts scan-repo")
    demo_cast = build_asciicast(_DEMO_TRANSCRIPT, title="telemetry-contracts scan-repo")
    card = render_social_card(
        headline=_HEADLINE,
        score=99,
        score_label="median diagnosability score",
    )

    (_OUT / "demo.svg").write_text(demo_svg, encoding="utf-8")
    (_OUT / "demo.cast").write_text(demo_cast, encoding="utf-8")
    (_OUT / "social_card.svg").write_text(card, encoding="utf-8")
    (_OUT / "demo_transcript.txt").write_text(_DEMO_TRANSCRIPT, encoding="utf-8")
    return {
        "demo_svg": str(_OUT / "demo.svg"),
        "demo_cast": str(_OUT / "demo.cast"),
        "social_card": str(_OUT / "social_card.svg"),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(build(), indent=2, sort_keys=True))
