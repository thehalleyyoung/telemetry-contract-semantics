"""Single source of truth for the observability *bug classes* this tool detects.

The project's thesis is that **observability is a correctness property**:
under-instrumentation is a detectable bug class, not a matter of taste. This
module names each bug class once — with a testable definition, the diagnose/
analyze finding codes that witness it, an incident question it blocks, and an
explicit **soundness / incompleteness statement** — so the documentation, the
finding taxonomy, the corpus study, and any future paper all derive from the
same place and can never silently drift apart.

Everything here is plain data (no wall-clock, no RNG); callers render it
deterministically.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Bug-class catalogue
# ---------------------------------------------------------------------------
#
# Each entry is keyed by a stable ``gap`` id (the same ids the pipeline's
# ``diagnose`` uses for blocked-question accounting). Fields:
#
# * ``title``           — short human label.
# * ``definition``      — a precise, testable statement of what counts as an
#                         instance of this bug class.
# * ``blocks_question`` — the incident question an instance makes unanswerable.
# * ``finding_codes``   — the existing TAXONOMY/discovery codes that witness it
#                         (we never invent new ``Finding.code`` values here).
# * ``detector``        — which engine surface detects it.
# * ``guarantee``       — what a *finding* of this class soundly establishes.
# * ``incompleteness``  — what a *clean* result does NOT establish (the known
#                         false-negative sources).
# * ``false_positive_sources`` — known causes of spurious findings.

BUG_CLASSES: dict[str, dict[str, Any]] = {
    "missing-correlation": {
        "title": "Failure without correlation id",
        "definition": (
            "An event classified as a failure (error/critical severity, or an "
            "ok/status/success field indicating failure) that carries no "
            "correlation identifier (trace_id, traceId, request_id, span_id, or "
            "a recognised alias)."
        ),
        "blocks_question": "Why did this request fail (which trace/request was it)?",
        "finding_codes": ["telemetry.correlation_missing"],
        "detector": "analyze/diagnose (data)",
        "guarantee": (
            "If reported, the sampled failure event provably lacks any recognised "
            "correlation field, so it cannot be joined to a distributed trace or "
            "request timeline from the telemetry alone."
        ),
        "incompleteness": (
            "A clean result only covers sampled events and recognised correlation "
            "aliases; a correlation id under an unrecognised key, or failures not "
            "present in the sampled data, are not detected."
        ),
        "false_positive_sources": (
            "An event mislabelled as a failure (heuristic severity inference), or "
            "a correlation id embedded inside a composite/nested field we do not "
            "flatten."
        ),
    },
    "missing-error-evidence": {
        "title": "Failure without error evidence",
        "definition": (
            "A failure event that carries no error code, exception type, or status "
            "evidence field (error_code, exception, exception_type, status, "
            "status_code, or a recognised alias)."
        ),
        "blocks_question": "What error caused this failure?",
        "finding_codes": ["discovery.missing_error_evidence"],
        "detector": "analyze/diagnose (data)",
        "guarantee": (
            "If reported, the sampled failure event provably lacks any recognised "
            "error-evidence field, so its root cause is not recoverable from the "
            "event itself."
        ),
        "incompleteness": (
            "Only sampled failures and recognised evidence aliases are covered; "
            "error detail carried in a free-text message we do not parse is not "
            "credited."
        ),
        "false_positive_sources": (
            "A mislabelled failure, or error detail present only in an unstructured "
            "message field."
        ),
    },
    "missing-duration": {
        "title": "Span without duration",
        "definition": (
            "An event whose kind is span/spans that carries no duration measure "
            "(duration_ms, duration, elapsed_ms, latency_ms, or a recognised "
            "alias)."
        ),
        "blocks_question": "How long did this operation take?",
        "finding_codes": ["telemetry.missing_field"],
        "detector": "analyze/diagnose (data)",
        "guarantee": (
            "If reported, the sampled span provably lacks any recognised duration "
            "field, so latency cannot be computed from the span alone."
        ),
        "incompleteness": (
            "Only events whose kind is inferred as a span are considered; spans "
            "mislabelled as plain events, or duration recoverable from separate "
            "start/end timestamps, are not detected."
        ),
        "false_positive_sources": (
            "A non-span event misclassified as a span by kind inference."
        ),
    },
    "sensitive-values": {
        "title": "Raw sensitive value in telemetry",
        "definition": (
            "A scalar field whose value matches a high-precision raw-secret/PII "
            "pattern (email, bearer token, JWT, password assignment, or a "
            "card/phone value in a card/phone-named field)."
        ),
        "blocks_question": "Is this telemetry safe to retain and share?",
        "finding_codes": ["telemetry.sensitive_value"],
        "detector": "analyze/diagnose (data)",
        "guarantee": (
            "If reported, the sampled value matches a deliberately conservative "
            "raw-secret/PII pattern, indicating unredacted sensitive data is "
            "present in telemetry."
        ),
        "incompleteness": (
            "Patterns are tuned for precision over recall; obfuscated, encoded, or "
            "domain-specific secrets, and secrets in unsampled events, are not "
            "detected."
        ),
        "false_positive_sources": (
            "A synthetic/example value (e.g. test fixtures) that matches the "
            "pattern but is not real production data."
        ),
    },
    "unclassified-sensitive": {
        "title": "Unclassified sensitive / tenant identifier",
        "definition": (
            "A field whose name indicates a tenant/customer/account/user "
            "identifier or sensitive attribute, emitted without redaction/hashing "
            "and without a privacy classification."
        ),
        "blocks_question": "Which fields carry regulated or tenant-scoped data?",
        "finding_codes": ["telemetry.sensitive_unclassified"],
        "detector": "analyze/diagnose (data)",
        "guarantee": (
            "If reported, a field named like a sensitive/tenant identifier is "
            "emitted in the clear with no declared privacy handling."
        ),
        "incompleteness": (
            "Name-based; a sensitive field with an innocuous name is not flagged, "
            "and a benign field with a sensitive-looking name may be."
        ),
        "false_positive_sources": (
            "A field whose name resembles a sensitive identifier but whose value "
            "is non-sensitive (e.g. a public account slug)."
        ),
    },
    "unbounded-cardinality": {
        "title": "Unbounded metric label cardinality",
        "definition": (
            "A metric label whose distinct-value count across the sampled points "
            "is high relative to the sample (sample-size gated), indicating likely "
            "unbounded cardinality."
        ),
        "blocks_question": "Will this metric explode storage / cost as it scales?",
        "finding_codes": ["telemetry.cardinality"],
        "detector": "analyze/diagnose (data)",
        "guarantee": (
            "If reported, the sampled metric label exhibits a distinct-value ratio "
            "consistent with unbounded cardinality at scale."
        ),
        "incompleteness": (
            "Gated on sample size; labels that are unbounded only beyond the "
            "sampled window are not detected, and bursty-but-bounded labels may be "
            "flagged."
        ),
        "false_positive_sources": (
            "A bounded label that happens to be near-unique within a small sample."
        ),
    },
}

# Ordered list of gap ids (deterministic iteration order independent of dict
# insertion details).
BUG_CLASS_IDS: list[str] = sorted(BUG_CLASSES)

# The single incident question whose blocking drives the project's headline
# statistic ("what fraction of real repositories cannot answer this?").
HEADLINE_GAP = "missing-correlation"
HEADLINE_QUESTION = BUG_CLASSES[HEADLINE_GAP]["blocks_question"]

# Map every witnessing finding code back to its bug class, for classifying a
# scan's findings into bug-class buckets.
CODE_TO_BUG_CLASS: dict[str, str] = {
    code: gap
    for gap, entry in sorted(BUG_CLASSES.items())
    for code in entry["finding_codes"]
}


def classify_finding_code(code: str) -> str | None:
    """Return the bug-class id a finding ``code`` witnesses, or ``None``."""

    return CODE_TO_BUG_CLASS.get(code)


def soundness_rows() -> list[dict[str, Any]]:
    """Return the per-class soundness/incompleteness rows (deterministic order)."""

    rows: list[dict[str, Any]] = []
    for gap in BUG_CLASS_IDS:
        entry = BUG_CLASSES[gap]
        rows.append(
            {
                "id": gap,
                "title": entry["title"],
                "definition": entry["definition"],
                "blocks_question": entry["blocks_question"],
                "finding_codes": list(entry["finding_codes"]),
                "detector": entry["detector"],
                "guarantee": entry["guarantee"],
                "incompleteness": entry["incompleteness"],
                "false_positive_sources": entry["false_positive_sources"],
            }
        )
    return rows
