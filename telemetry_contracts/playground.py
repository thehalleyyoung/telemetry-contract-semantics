"""Single-call entrypoint for the zero-install browser playground.

The browser playground (``playground/``) runs the *pure-stdlib* engine entirely
client-side under Pyodide — no backend. To keep the JavaScript glue trivial and
to share one tested code path with the CLI, this module exposes a single
function, :func:`analyze_text`, that takes a blob of telemetry *text* in whatever
shape the visitor already has (JSON lines, a JSON array, logfmt, or an OTLP JSON
export), auto-detects the format, runs the zero-config gap analysis plus the
diagnosability score, and returns a compact, JSON-serializable report.

Determinism: the result is a pure function of the input text and ``service`` —
no wall-clock, no RNG, sorted aggregates — so the same paste always yields the
same report (snapshot-tested), which is what makes shareable, URL-encoded
playground results reproducible.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

from .adapters import load_events_auto
from .discover import analyze_events
from .pipeline import diagnose

__all__ = ["analyze_text"]


def analyze_text(text: str, *, service: str | None = None, source_name: str = "pasted.jsonl") -> dict[str, Any]:
    """Analyze pasted telemetry text and return a compact, JSON-able report.

    ``text`` is parsed best-effort (``tolerant=True``) so a few unparseable lines
    do not abort the analysis; they are surfaced in ``parse_diagnostics``. The
    report combines the gap findings (:func:`analyze_events`) with the
    diagnosability score and unanswered incident questions (:func:`diagnose`).
    """

    suffix = ".jsonl"
    lowered = source_name.lower()
    if lowered.endswith(".json"):
        suffix = ".json"
    elif lowered.endswith(".logfmt") or lowered.endswith(".log"):
        suffix = lowered[lowered.rfind("."):]

    tmp_dir = tempfile.mkdtemp(prefix="telemetry-contracts-playground-")
    path = os.path.join(tmp_dir, "pasted" + suffix)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)

    loaded = load_events_auto(path, tolerant=True)
    events = loaded["events"]

    analysis = analyze_events(events, service=service)
    diag = diagnose(events, service=service)

    by_code = analysis["summary"]["by_code"]
    top_gaps = [
        {"code": code, "count": by_code[code]}
        for code in sorted(by_code, key=lambda c: (-by_code[c], c))
    ]

    return {
        "schema": "telemetry-contracts/playground@1",
        "format": loaded["format"],
        "event_count": len(events),
        "service": service,
        "diagnosability_score": diag["diagnosability_score"],
        "verdict": diag["verdict"],
        "has_telemetry": len(events) > 0,
        "findings": analysis["findings"],
        "by_severity": analysis["summary"]["by_severity"],
        "top_gaps": top_gaps,
        "unanswered_questions": [
            {"id": q["id"], "question": q["question"], "gap": q.get("gap")}
            for q in diag["unanswered_questions"]
        ],
        "parse_diagnostics": loaded.get("diagnostics", []),
    }
