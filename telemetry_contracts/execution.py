"""Safe execution proof for *our own* generated instrumentation snippets.

This module produces runtime evidence that the deterministically generated
instrumentation proposals (see :mod:`telemetry_contracts.code_proposals`) compile,
import, and — for the stdlib ``logging`` variant — actually emit telemetry that
carries the promised field names. It never executes the target repository's code
and never trusts proposal-carried snippet text: every snippet is regenerated from
the trusted ``(gap, library_kind)`` fields, AST-validated against a strict
allowlist, and run in a hardened, isolated subprocess.

Honesty boundary: this is an *isolated generated-instrumentation
compile/load/emission proof*. It is deliberately NOT the target repository's
build or test suite, which is intentionally never run in a shared environment.
Executed events are evidence only — they are never folded into scoring or the
differential, so the deterministic scores are unaffected.
"""

from __future__ import annotations

import ast
import json
import keyword
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .code_proposals import _INTENDED_NAMES, _render_snippet

# --- status taxonomy -------------------------------------------------------
STATUS_BUILD_CLEAN = "build-clean"
STATUS_EMISSION_CLEAN = "emission-clean"
STATUS_NEEDS_DEP = "needs-optional-dep"
STATUS_UNSAFE = "not-executed-unsafe"
STATUS_INVALID_NAMES = "not-executed-invalid-names"
STATUS_UNAVAILABLE = "execution-unavailable"
STATUS_TIMEOUT = "execution-timeout"
STATUS_CRASHED = "execution-crashed"

EXECUTION_PROOF_SCHEMA = "telemetry-contracts/execution-proof@1"
_LOGGER_NAME = "telemetry-contracts.proposal"
_SUPPORTED_KINDS = ("logging", "opentelemetry")
DEFAULT_TIMEOUT = 10

# Names that may never appear anywhere in a validated snippet.
_FORBIDDEN_NAMES = frozenset(
    {
        "eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr",
        "open", "os", "sys", "subprocess", "socket", "importlib", "globals",
        "locals", "vars", "input", "breakpoint", "__builtins__", "shutil",
        "pathlib", "ctypes", "marshal", "pickle", "code", "pty", "signal",
    }
)
# LogRecord reserved attributes — an intended field colliding with one of these
# makes ``logging`` raise at call time, so we refuse to execute it.
_LOGRECORD_RESERVED = frozenset(
    logging.makeLogRecord({}).__dict__.keys()
) | {"message", "asctime"}


def validate_intended_names(names: list[str]) -> tuple[bool, str]:
    """Reject field names that are unsafe or undefined to execute."""

    if not names:
        return False, "no intended field names for this gap"
    for name in names:
        if not isinstance(name, str) or not name.isidentifier():
            return False, f"field {name!r} is not a valid identifier"
        if keyword.iskeyword(name) or keyword.issoftkeyword(name):
            return False, f"field {name!r} is a Python keyword"
        if name in _LOGRECORD_RESERVED:
            return False, f"field {name!r} collides with a reserved LogRecord attribute"
    return True, "ok"


def _attr_is_dunder(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr.startswith("__")


def validate_snippet_ast(snippet: str, library_kind: str) -> dict[str, Any]:
    """Strict, exact-shape allowlist validation of a regenerated snippet.

    Validates module shape (imports, one module-level helper assignment, one
    ``annotate`` function) and scans every node for forbidden names / dunder
    attribute access. Returns ``{"ok": bool, "reason": str}``.
    """

    try:
        tree = ast.parse(snippet)
    except SyntaxError as exc:
        return {"ok": False, "reason": f"syntax error: {exc.msg}"}

    # Whole-tree security scan: no forbidden names, no dunder attribute access.
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            return {"ok": False, "reason": f"forbidden name: {node.id}"}
        if _attr_is_dunder(node):
            return {"ok": False, "reason": f"dunder attribute access: {node.attr}"}
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for mod in modules:
                head = mod.split(".")[0]
                if head not in {"logging", "opentelemetry"}:
                    return {"ok": False, "reason": f"forbidden import: {mod}"}

    body = tree.body
    func_defs = [n for n in body if isinstance(n, ast.FunctionDef)]
    if len(func_defs) != 1 or func_defs[0].name != "annotate":
        return {"ok": False, "reason": "expected exactly one module-level def annotate"}
    if any(isinstance(n, (ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)) for n in ast.walk(tree)):
        return {"ok": False, "reason": "async/class/lambda not permitted"}

    imports = [n for n in body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assigns = [n for n in body if isinstance(n, ast.Assign)]
    if len(imports) != 1 or len(assigns) != 1:
        return {"ok": False, "reason": "expected exactly one import and one module-level assignment"}
    target = assigns[0].targets
    if len(target) != 1 or not isinstance(target[0], ast.Name) or target[0].id not in {"logger", "tracer"}:
        return {"ok": False, "reason": "module assignment must bind logger or tracer"}

    if library_kind == "logging":
        if not (isinstance(imports[0], ast.Import) and imports[0].names[0].name == "logging"):
            return {"ok": False, "reason": "logging variant must import logging"}
    else:
        imp = imports[0]
        if not (isinstance(imp, ast.ImportFrom) and imp.module == "opentelemetry"):
            return {"ok": False, "reason": "opentelemetry variant must import from opentelemetry"}

    # Reject any node type outside the small set the templates emit.
    allowed = (
        ast.Module, ast.Import, ast.ImportFrom, ast.alias, ast.Assign, ast.Name,
        ast.Store, ast.Load, ast.Call, ast.Attribute, ast.Constant, ast.Expr,
        ast.FunctionDef, ast.arguments, ast.arg, ast.With, ast.withitem,
        ast.Dict, ast.keyword,
    )
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            return {"ok": False, "reason": f"disallowed AST node: {type(node).__name__}"}
    return {"ok": True, "reason": "ok"}


def _setrlimits() -> None:  # pragma: no cover - POSIX child process only
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (2, 3))
        # Cap file size (we only print to a pipe); do NOT cap address space —
        # RLIMIT_AS makes interpreter startup flaky across platforms.
        resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
    except Exception:
        pass


def _run_driver(driver_src: str, timeout: int) -> tuple[Any, str, str]:
    """Run a self-contained driver in a hardened, isolated subprocess."""

    tmp = tempfile.mkdtemp(prefix="telemetry-contracts-exec-")
    try:
        driver = Path(tmp) / "driver.py"
        driver.write_text(driver_src, encoding="utf-8")
        kwargs: dict[str, Any] = {}
        if os.name == "posix":
            kwargs["preexec_fn"] = _setrlimits
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-E", str(driver)],
                cwd=tmp,
                env={"PATH": "/usr/bin:/bin"},
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                close_fds=True,
                **kwargs,
            )
        except subprocess.TimeoutExpired:
            return ("timeout", "", "")
        return (proc.returncode, proc.stdout, proc.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _logging_driver(snippet: str, names: list[str]) -> str:
    call_args = ", ".join(repr(v) for v in ["operation", *names])
    name_literal = ", ".join(repr(n) for n in names)
    return (
        snippet
        + "\n\n"
        + "import json as _json\n"
        + "import logging as _logging\n\n"
        + "class _Cap(_logging.Handler):\n"
        + "    def __init__(self):\n"
        + "        super().__init__()\n"
        + "        self.records = []\n"
        + "    def emit(self, record):\n"
        + "        self.records.append(record)\n\n"
        + "def _main():\n"
        + f"    _cap = _Cap()\n"
        + f"    _lg = _logging.getLogger({_LOGGER_NAME!r})\n"
        + "    _lg.handlers = [_cap]\n"
        + "    _lg.propagate = False\n"
        + "    _lg.setLevel(_logging.DEBUG)\n"
        + f"    annotate({call_args})\n"
        + f"    _intended = [{name_literal}]\n"
        + "    _events = []\n"
        + "    for _r in _cap.records:\n"
        + "        _fields = sorted(n for n in _intended if hasattr(_r, n))\n"
        + "        _events.append({\n"
        + "            'source': 'executed-instrumentation',\n"
        + "            'level': _r.levelname,\n"
        + "            'message': _r.getMessage(),\n"
        + "            'fields': _fields,\n"
        + "        })\n"
        + "    print(_json.dumps({'status': 'ok', 'events': _events}, sort_keys=True, separators=(',', ':')))\n\n"
        + "_main()\n"
    )


def _otel_available(timeout: int) -> bool:
    rc, _out, _err = _run_driver("import opentelemetry\n", timeout)
    return rc == 0


def _build_load_driver(snippet: str) -> str:
    # Import-only proof: defining the module top-to-bottom exercises the import
    # and the def; we then confirm annotate is callable without invoking it.
    return snippet + "\nassert callable(annotate)\nprint('build-clean')\n"


def execute_proposal(
    *, gap: str, library_kind: str, timeout: int = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Produce a safe execution proof for a single proposal's trusted fields.

    Only ``gap`` and ``library_kind`` are trusted; the snippet is regenerated
    from them (never read from proposal text). Returns a deterministic verdict.
    """

    result: dict[str, Any] = {
        "gap": gap,
        "library_kind": library_kind,
        "status": STATUS_UNAVAILABLE,
        "detail": "",
        "build": {"compile_ok": None, "import_ok": None},
        "events": [],
        "isolation": {
            "interpreter_flags": ["-I", "-S", "-B", "-E"],
            "target_repo_build_not_run": True,
            "executed_target_repo_code": False,
        },
    }

    if library_kind not in _SUPPORTED_KINDS:
        result["status"] = STATUS_UNAVAILABLE
        result["detail"] = f"unsupported library_kind: {library_kind!r}"
        return result

    names = list(_INTENDED_NAMES.get(gap, []))
    names_ok, names_reason = validate_intended_names(names)
    if not names_ok:
        result["status"] = STATUS_INVALID_NAMES
        result["detail"] = names_reason
        return result

    snippet = _render_snippet(library_kind, gap, names)
    ast_check = validate_snippet_ast(snippet, library_kind)
    result["ast_validation"] = ast_check
    if not ast_check["ok"]:
        result["status"] = STATUS_UNSAFE
        result["detail"] = ast_check["reason"]
        return result

    # Host-side compile is a safe (non-executing) precheck.
    try:
        compile(snippet, "<proposal>", "exec")
        result["build"]["compile_ok"] = True
    except (SyntaxError, ValueError) as exc:
        result["build"]["compile_ok"] = False
        result["status"] = STATUS_CRASHED
        result["detail"] = f"compile failed: {exc}"
        return result

    if library_kind == "opentelemetry":
        if not _otel_available(timeout):
            result["status"] = STATUS_NEEDS_DEP
            result["detail"] = "opentelemetry not importable under isolated python (-S); install the SDK to prove emission"
            return result
        rc, _out, err = _run_driver(_build_load_driver(snippet), timeout)
        if rc == "timeout":
            result["status"] = STATUS_TIMEOUT
            result["detail"] = f"build/load timed out after {timeout}s"
        elif rc == 0:
            result["build"]["import_ok"] = True
            result["status"] = STATUS_BUILD_CLEAN
            result["detail"] = "compiled and imported in isolated subprocess (emission requires the OTel SDK exporter)"
        else:
            result["build"]["import_ok"] = False
            result["status"] = STATUS_CRASHED
            result["detail"] = (err.strip().splitlines() or ["nonzero exit"])[-1]
        return result

    # logging variant: prove emission of the promised fields.
    rc, out, err = _run_driver(_logging_driver(snippet, names), timeout)
    if rc == "timeout":
        result["status"] = STATUS_TIMEOUT
        result["detail"] = f"execution timed out after {timeout}s"
        return result
    if rc != 0:
        result["build"]["import_ok"] = False
        result["status"] = STATUS_CRASHED
        result["detail"] = (err.strip().splitlines() or ["nonzero exit"])[-1]
        return result
    try:
        payload = json.loads(out.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        result["status"] = STATUS_CRASHED
        result["detail"] = "could not parse driver output"
        return result

    result["build"]["import_ok"] = True
    events = payload.get("events", [])
    result["events"] = events
    emitted_fields = sorted({f for e in events for f in e.get("fields", [])})
    if events and emitted_fields == sorted(names):
        result["status"] = STATUS_EMISSION_CLEAN
        result["detail"] = f"emitted {len(events)} record(s) carrying fields: {emitted_fields}"
    elif events:
        result["status"] = STATUS_BUILD_CLEAN
        result["detail"] = f"emitted records but fields {emitted_fields} != promised {sorted(names)}"
    else:
        result["status"] = STATUS_BUILD_CLEAN
        result["detail"] = "imported cleanly but emitted no records"
    return result


def execution_proof(
    proposals: list[dict[str, Any]], *, timeout: int = DEFAULT_TIMEOUT
) -> dict[str, Any]:
    """Aggregate, deterministic execution proof over a list of proposals.

    Reads only each proposal's trusted ``gap`` and ``library_kind`` (never the
    stored snippet). Deduplicates identical (gap, library_kind) pairs so the
    proof is stable regardless of proposal multiplicity.
    """

    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for proposal in proposals:
        gap = str(proposal.get("gap", ""))
        kind = str(proposal.get("library_kind", ""))
        key = (gap, kind)
        if key not in seen:
            seen[key] = execute_proposal(gap=gap, library_kind=kind, timeout=timeout)

    proofs = [seen[k] for k in sorted(seen)]
    counts: dict[str, int] = {}
    for p in proofs:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    return {
        "schema": EXECUTION_PROOF_SCHEMA,
        "is_repository_finding": False,
        "honesty": (
            "Isolated generated-instrumentation compile/load/emission proof; the "
            "target repository's build/test is intentionally not run in a shared "
            "environment. Executed events are evidence only and never scored."
        ),
        "proofs": proofs,
        "summary": {
            "proposals": len(proofs),
            "status_counts": {k: counts[k] for k in sorted(counts)},
            "all_logging_emit_clean": all(
                p["status"] == STATUS_EMISSION_CLEAN
                for p in proofs
                if p["library_kind"] == "logging"
            ),
        },
    }


def render_execution_proof_markdown(proof: dict[str, Any]) -> str:
    s = proof["summary"]
    lines = [
        "# Execution proof: generated instrumentation",
        "",
        f"> {proof['honesty']}",
        "",
        f"**{s['proposals']}** proposal(s) proved; status counts: "
        + ", ".join(f"`{k}`={v}" for k, v in s["status_counts"].items())
        + ".",
        "",
        "| Gap | Library | Status | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for p in proof["proofs"]:
        lines.append(
            f"| `{p['gap']}` | {p['library_kind']} | `{p['status']}` | {p['detail']} |"
        )
    return "\n".join(lines) + "\n"
