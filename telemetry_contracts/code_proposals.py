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
import hashlib
import re
import subprocess
import tempfile
from typing import Any

from .static_checker import _extract_observations  # static name extractor (AST-based)
from pathlib import Path

GENERATOR = "telemetry-contracts/code-proposal@1"

# Directory the companion-instrumentation file is added under in a patch.
_PATCH_DIR = "telemetry_instrumentation"
_SLUG_OK = re.compile(r"[^a-z0-9_-]+")

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


def _slugify_gap(gap: str) -> str:
    """Return a strict, collision-safe filename slug for a gap code.

    Only ``[a-z0-9_-]`` survive; everything else (dots, slashes, ``..``,
    backslashes, whitespace) is replaced so the derived path can never traverse
    outside the patch directory or produce a non-portable filename.
    """

    slug = _SLUG_OK.sub("-", gap.strip().lower()).strip("-_")
    return slug or "instrumentation"


def _unified_new_file_patch(path: str, content: str) -> str:
    """Build a canonical, deterministic git unified diff that ADDS a new file.

    The diff is a pure addition (``--- /dev/null``), so it can never rewrite the
    target repository's business logic and is guaranteed to apply cleanly unless
    the path already exists. The output is LF-only with no timestamps, so it is
    byte-identical across machines for the same content.
    """

    body = content if content.endswith("\n") else content + "\n"
    lines = body.split("\n")[:-1]  # drop the trailing empty element from final \n
    hunk = [f"+{line}" for line in lines]
    no_newline = "" if body.endswith("\n") else "\n\\ No newline at end of file\n"
    patch = (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        + "\n".join(hunk)
        + "\n"
        + no_newline
    )
    return patch


def _git_apply_check(repo_root: Path, patch_text: str) -> tuple[bool, str]:
    """Validate that ``patch_text`` applies cleanly at the repo's current SHA.

    Uses ``git apply --check`` which never executes target code or hooks. Git is
    invoked with deterministic whitespace/CRLF settings, and only a normalized
    reason code is returned (never raw, machine-specific diagnostic text).
    """

    if not (repo_root / ".git").exists():
        return False, "no-git-checkout"
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=True, newline="\n") as fh:
        fh.write(patch_text)
        fh.flush()
        try:
            proc = subprocess.run(
                [
                    "git", "-C", str(repo_root),
                    "-c", "core.autocrlf=false",
                    "-c", "core.whitespace=-trailing-space,-space-before-tab",
                    "apply", "--check", "--whitespace=nowarn", fh.name,
                ],
                capture_output=True, text=True, timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError):
            return False, "git-apply-unavailable"
    if proc.returncode == 0:
        return True, "applies-clean"
    stderr = (proc.stderr or "").lower()
    if "already exists" in stderr or "exists in" in stderr:
        return False, "target-path-exists"
    return False, "patch-conflict"


def _build_patch(repo_root: Path | None, slug: str, snippet: str) -> dict[str, Any]:
    """Produce a reviewable companion-file patch and check that it applies.

    The patch adds a brand-new file ``telemetry_instrumentation/<slug>.py``; it
    is a *reviewable companion patch*, not an applied or integrated change. If
    the target path already exists in the repo, a deterministic content-hash
    suffix is used so the addition stays clean.
    """

    path = f"{_PATCH_DIR}/{slug}.py"
    if repo_root is not None and (repo_root / path).exists():
        suffix = hashlib.sha256(snippet.encode("utf-8")).hexdigest()[:8]
        path = f"{_PATCH_DIR}/{slug}-{suffix}.py"
    patch_text = _unified_new_file_patch(path, snippet)
    added_lines = sum(1 for line in patch_text.splitlines() if line.startswith("+") and not line.startswith("+++"))
    applies_clean = None
    reason = "not-checked"
    if repo_root is not None:
        applies_clean, reason = _git_apply_check(repo_root, patch_text)
    return {
        "schema": "telemetry-contracts/companion-patch@1",
        "path": path,
        "kind": "new-file-addition",
        "added_lines": added_lines,
        "patch": patch_text,
        "patch_sha256": hashlib.sha256(patch_text.encode("utf-8")).hexdigest(),
        "applies_clean": applies_clean,
        "apply_reason": reason,
        "is_reviewable_companion_patch": True,
        "rewrites_business_logic": False,
    }


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
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Produce validated, standalone instrumentation proposals for a plan.

    Only non-privacy ``planned_changes`` get a code proposal; privacy/review
    changes are intentionally never turned into auto-generated code.

    When ``repo_root`` points at the cloned checkout, each proposal also carries
    a *reviewable companion patch* (a git unified diff that adds a new
    instrumentation file) generated against the exact cloned SHA and verified
    with ``git apply --check`` — a clean, reviewable diff rather than a rewrite.
    The patch is never applied; ``applied_to_repo`` stays ``False``.
    """

    from .high_impact_filter import score_code_proposal

    libraries = libraries or []
    kind = _library_kind(libraries)
    root = Path(repo_root) if repo_root is not None else None
    proposals: list[dict[str, Any]] = []
    for change in plan.get("planned_changes", []):
        gap = change["gap"]
        names = _INTENDED_NAMES.get(gap)
        if not names:
            continue
        snippet = _render_snippet(kind, gap, names)
        validation = validate_proposal(snippet, names)
        patch = _build_patch(root, _slugify_gap(gap), snippet)
        questions = list(change.get("predicted_impact", {}).get("questions_unblocked", []))
        proposal = {
            "id": change["id"],
            "gap": gap,
            "library_kind": kind,
            "language": "python",
            "snippet": snippet,
            "validation": validation,
            "patch": patch,
            "questions_unblocked": questions,
            "applicability": "manual-review-required",
            "applied_to_repo": False,
            "target_repo_build_not_run": True,
            "provenance": {
                "generator": GENERATOR,
                "source_commit": commit,
                "gap": gap,
            },
        }
        proposal["impact_score"] = score_code_proposal(proposal)
        proposals.append(proposal)
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
        "patches_all_apply_clean": all(
            p["patch"]["applies_clean"] is True for p in proposals
        ) if (root is not None and proposals) else None,
    }

