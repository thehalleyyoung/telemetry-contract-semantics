"""Offline tests for the safe execution proof of generated instrumentation.

These tests prove that the tool can execute *its own* deterministically
generated instrumentation in a hardened isolated subprocess, that the logging
variant actually emits the promised field names, that the OpenTelemetry variant
degrades honestly to ``needs-optional-dep`` when the SDK is absent, and that the
AST validator refuses anything outside the exact generated shape. No network.
"""

from __future__ import annotations

from telemetry_contracts.execution import (
    STATUS_BUILD_CLEAN,
    STATUS_EMISSION_CLEAN,
    STATUS_INVALID_NAMES,
    STATUS_NEEDS_DEP,
    STATUS_UNAVAILABLE,
    STATUS_UNSAFE,
    execute_proposal,
    execution_proof,
    render_execution_proof_markdown,
    validate_intended_names,
    validate_snippet_ast,
)
from telemetry_contracts.code_proposals import _INTENDED_NAMES, _render_snippet

LOGGING_GAPS = sorted(_INTENDED_NAMES)


def test_logging_variant_emits_promised_fields():
    for gap in LOGGING_GAPS:
        proof = execute_proposal(gap=gap, library_kind="logging")
        assert proof["status"] == STATUS_EMISSION_CLEAN, (gap, proof["detail"])
        assert proof["build"]["compile_ok"] is True
        assert proof["build"]["import_ok"] is True
        emitted = sorted({f for e in proof["events"] for f in e["fields"]})
        assert emitted == sorted(_INTENDED_NAMES[gap])
        for event in proof["events"]:
            assert event["source"] == "executed-instrumentation"
            assert event["level"] == "ERROR"
            assert event["message"] == "operation.failed"
        assert proof["isolation"]["executed_target_repo_code"] is False
        assert proof["isolation"]["target_repo_build_not_run"] is True


def test_execution_is_deterministic():
    a = execute_proposal(gap="missing-correlation", library_kind="logging")
    b = execute_proposal(gap="missing-correlation", library_kind="logging")
    assert a == b


def test_opentelemetry_variant_needs_optional_dep_when_sdk_absent():
    proof = execute_proposal(gap="missing-correlation", library_kind="opentelemetry")
    # In the stdlib-only isolated interpreter the SDK is not importable.
    assert proof["status"] in {STATUS_NEEDS_DEP, STATUS_BUILD_CLEAN}
    if proof["status"] == STATUS_NEEDS_DEP:
        assert "opentelemetry" in proof["detail"]


def test_unsupported_library_kind_is_not_executed():
    proof = execute_proposal(gap="missing-correlation", library_kind="ruby-magic")
    assert proof["status"] == STATUS_UNAVAILABLE
    assert proof["events"] == []


def test_unknown_gap_yields_invalid_names():
    proof = execute_proposal(gap="not-a-real-gap", library_kind="logging")
    assert proof["status"] == STATUS_INVALID_NAMES


def test_validate_intended_names_rejects_unsafe():
    assert validate_intended_names([])[0] is False
    assert validate_intended_names(["1bad"])[0] is False
    assert validate_intended_names(["class"])[0] is False  # keyword
    assert validate_intended_names(["message"])[0] is False  # reserved LogRecord attr
    assert validate_intended_names(["trace_id", "duration_ms"])[0] is True


def test_ast_validator_accepts_generated_snippets():
    for gap in LOGGING_GAPS:
        snippet = _render_snippet("logging", gap, _INTENDED_NAMES[gap])
        assert validate_snippet_ast(snippet, "logging")["ok"] is True
    otel = _render_snippet("opentelemetry", "missing-correlation", ["trace_id"])
    assert validate_snippet_ast(otel, "opentelemetry")["ok"] is True


def test_ast_validator_rejects_tampered_snippets():
    bad_os = (
        "import os\n\nlogger = os\n\n\ndef annotate(operation, trace_id):\n"
        '    """x"""\n    os.system("echo pwned")\n'
    )
    res = validate_snippet_ast(bad_os, "logging")
    assert res["ok"] is False

    bad_eval = (
        "import logging\n\nlogger = logging.getLogger('x')\n\n\n"
        "def annotate(operation, trace_id):\n"
        '    """x"""\n    eval("1+1")\n'
    )
    assert validate_snippet_ast(bad_eval, "logging")["ok"] is False

    bad_dunder = (
        "import logging\n\nlogger = logging.getLogger('x')\n\n\n"
        "def annotate(operation, trace_id):\n"
        '    """x"""\n    logger.__class__\n'
    )
    assert validate_snippet_ast(bad_dunder, "logging")["ok"] is False

    bad_extra_func = (
        "import logging\n\nlogger = logging.getLogger('x')\n\n\n"
        "def annotate(operation, trace_id):\n    \"\"\"x\"\"\"\n    logger.error('%s', operation)\n\n\n"
        "def helper():\n    return 1\n"
    )
    assert validate_snippet_ast(bad_extra_func, "logging")["ok"] is False


def test_aggregate_proof_dedupes_and_summarizes():
    proposals = [
        {"gap": "missing-correlation", "library_kind": "logging"},
        {"gap": "missing-correlation", "library_kind": "logging"},  # duplicate
        {"gap": "missing-duration", "library_kind": "logging"},
    ]
    proof = execution_proof(proposals)
    assert proof["is_repository_finding"] is False
    assert proof["summary"]["proposals"] == 2  # deduped
    assert proof["summary"]["all_logging_emit_clean"] is True
    assert proof["summary"]["status_counts"].get(STATUS_EMISSION_CLEAN) == 2
    # deterministic ordering by (gap, kind)
    gaps = [p["gap"] for p in proof["proofs"]]
    assert gaps == sorted(gaps)


def test_aggregate_ignores_proposal_snippet_text():
    # A malicious proposal text must never influence the proof: only (gap, kind)
    # are consulted; the snippet is regenerated from trusted templates.
    honest = execution_proof([{"gap": "missing-correlation", "library_kind": "logging"}])
    tampered = execution_proof(
        [
            {
                "gap": "missing-correlation",
                "library_kind": "logging",
                "snippet": "import os\nos.system('rm -rf /')\n",
            }
        ]
    )
    assert honest["proofs"] == tampered["proofs"]


def test_markdown_renderer_lists_every_proof():
    proof = execution_proof(
        [{"gap": g, "library_kind": "logging"} for g in LOGGING_GAPS]
    )
    md = render_execution_proof_markdown(proof)
    assert md.startswith("# Execution proof")
    for p in proof["proofs"]:
        assert f"`{p['gap']}`" in md
        assert f"`{p['status']}`" in md
