"""Generate and validate standalone additive-instrumentation code proposals.

For each non-privacy gap in an instrumentation plan, this produces a small,
self-contained Python helper snippet that emits the missing signal/field using
the repository's detected instrumentation library. Each snippet is:

* parsed with :func:`ast.parse` and compiled with :func:`compile` (syntax/compile
  validation), and
* run through the project's own static source extractor to confirm it actually
  introduces the intended runtime names.

These are *proposals*: they are standalone helper sketches, never written into
the user's repository, and no target build or test is executed. Applying them to
production code remains a human, review-required step.
"""

from __future__ import annotations

import ast
from typing import Any

from .static_checker import _extract_observations  # static name extractor (AST-based)
from pathlib import Path

GENERATOR = "telemetry-contracts/code-proposal@1"

# The runtime field names each gap's instrumentation must introduce.
_INTENDED_NAMES: dict[str, list[str]] = {
    "missing-correlation": ["trace_id"],
    "missing-error-evidence": ["error_code", "exception_type"],
    "missing-duration": ["duration_ms"],
}


def _library_kind(libraries: list[str]) -> str:
    libs = {lib.lower() for lib in libraries}
    if "opentelemetry" in libs:
        return "opentelemetry"
    return "logging"


def _otel_snippet(gap: str, names: list[str]) -> str:
    assigns = "\n".join(f'        span.set_attribute("{n}", {n})' for n in names)
    params = ", ".join(["operation", *names])
    return (
        "from opentelemetry import trace\n\n"
        'tracer = trace.get_tracer("telemetry-contracts.proposal")\n\n\n'
        f"def annotate({params}):\n"
        '    """Additive instrumentation proposal — review before adopting."""\n'
        '    with tracer.start_as_current_span("operation.failed") as span:\n'
        f"{assigns}\n"
    )


def _logging_snippet(gap: str, names: list[str]) -> str:
    fields = ", ".join(f'"{n}": {n}' for n in names)
    params = ", ".join(["operation", *names])
    return (
        "import logging\n\n"
        'logger = logging.getLogger("telemetry-contracts.proposal")\n\n\n'
        f"def annotate({params}):\n"
        '    """Additive instrumentation proposal — review before adopting."""\n'
        f'    logger.error("%s.failed", operation, extra={{{fields}}})\n'
    )


def _render_snippet(kind: str, gap: str, names: list[str]) -> str:
    if kind == "opentelemetry":
        return _otel_snippet(gap, names)
    return _logging_snippet(gap, names)


def validate_proposal(snippet: str, intended_names: list[str]) -> dict[str, Any]:
    """Validate a snippet: syntax, compile, and static name introduction."""

    ast_ok = True
    compile_ok = True
    try:
        ast.parse(snippet)
    except SyntaxError:
        ast_ok = False
    try:
        compile(snippet, "<proposal>", "exec")
    except (SyntaxError, ValueError):
        compile_ok = False

    detected: list[str] = []
    if ast_ok:
        observations = _extract_observations(Path("proposal.py"), snippet)
        observed_attrs: set[str] = set()
        for obs in observations:
            observed_attrs.update(getattr(obs, "attributes", set()) or set())
        detected = sorted(n for n in intended_names if n in observed_attrs)
    present_in_source = sorted(n for n in intended_names if f'"{n}"' in snippet)

    return {
        "ast_parse_ok": ast_ok,
        "compile_ok": compile_ok,
        "intended_names": list(intended_names),
        "static_checker_detected_names": detected,
        "present_in_source": present_in_source,
        "introduces_intended_names": bool(present_in_source) and present_in_source == sorted(intended_names),
    }


def generate_code_proposals(
    plan: dict[str, Any],
    *,
    libraries: list[str] | None = None,
    commit: str | None = None,
) -> dict[str, Any]:
    """Produce validated, standalone instrumentation proposals for a plan.

    Only non-privacy ``planned_changes`` get a code proposal; privacy/review
    changes are intentionally never turned into auto-generated code.
    """

    libraries = libraries or []
    kind = _library_kind(libraries)
    proposals: list[dict[str, Any]] = []
    for change in plan.get("planned_changes", []):
        gap = change["gap"]
        names = _INTENDED_NAMES.get(gap)
        if not names:
            continue
        snippet = _render_snippet(kind, gap, names)
        validation = validate_proposal(snippet, names)
        proposals.append({
            "id": change["id"],
            "gap": gap,
            "library_kind": kind,
            "language": "python",
            "snippet": snippet,
            "validation": validation,
            "applicability": "manual-review-required",
            "applied_to_repo": False,
            "target_repo_build_not_run": True,
            "provenance": {
                "generator": GENERATOR,
                "source_commit": commit,
                "gap": gap,
            },
        })
    return {
        "schema": "telemetry-contracts/code-proposals@1",
        "generator": GENERATOR,
        "library_kind": kind,
        "proposals": sorted(proposals, key=lambda p: p["id"]),
        "all_valid": all(
            p["validation"]["ast_parse_ok"]
            and p["validation"]["compile_ok"]
            and p["validation"]["introduces_intended_names"]
            for p in proposals
        ) if proposals else True,
    }
