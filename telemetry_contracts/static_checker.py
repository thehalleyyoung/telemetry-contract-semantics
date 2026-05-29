from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from .findings import Finding

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".cs", ".rb"}
SENSITIVE_NAMES = re.compile(r"(?i)(password|passwd|pwd|token|secret|authorization|auth[_-]?token|cookie|api[_-]?key|session[_-]?id)")
LOG_CALL = re.compile(r"(?i)\b(console\.(?:log|error|warn)|logger\.(?:error|warning|warn|info|debug)|log\.(?:Error|Warn|Info|Debug|Printf|Println)|print|printf)\b")
ERROR_WORDS = re.compile(r"(?i)(error|exception|failed|failure|unauthori[sz]ed|invalid credentials)")
METRIC_WORDS = re.compile(r"(?i)(counter|histogram|gauge|metric|labels?|tags?|attributes?)")
HIGH_CARD_NAMES = re.compile(r"(?i)(user(name)?|email|ip|url|path|session|cookie|cart|order|request|trace)")


def expected_names(contract: dict[str, Any]) -> dict[str, list[str]]:
    configured = contract.get("static_expectations") or {}
    names: dict[str, list[str]] = {"spans": [], "metrics": [], "logs": []}
    for section in names:
        explicit = configured.get(section)
        if isinstance(explicit, list):
            names[section].extend(str(item) for item in explicit)
        else:
            names[section].extend(str(item.get("name")) for item in contract.get(section, []) if isinstance(item, dict) and item.get("required", True) and item.get("name"))
    return names


def check_sources(contract: dict[str, Any], source_paths: Iterable[str | Path]) -> list[Finding]:
    files = _collect_files(source_paths)
    texts = [(path, path.read_text(encoding="utf-8")) for path in files]
    corpus = "\n".join(text for _, text in texts)
    findings: list[Finding] = []
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for name in expected_names(contract)[section]:
            if name not in corpus:
                findings.append(Finding("error", "static.missing_instrumentation", f"expected {kind} name '{name}' was not found in source literals", "source", f"$.static_expectations.{section}", None, {"name": name}))
    for path, text in texts:
        findings.extend(_scan_source(path, text, contract))
    if not files:
        findings.append(Finding("warning", "static.no_sources", "no source files were checked", "source"))
    return findings


def _scan_source(path: Path, text: str, contract: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    rules = contract.get("static_rules") if isinstance(contract.get("static_rules"), dict) else {}
    require_correlation = bool(rules.get("require_correlation_on_error_logs"))
    detect_unbounded_labels = bool(rules.get("detect_unbounded_labels"))
    correlation_fields = [str(item) for item in rules.get("correlation_fields", ["trace_id", "traceId", "request_id", "requestId", "span_id"])]
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "#", "*")):
            continue
        location = f"{path}:{line_number}"
        if LOG_CALL.search(stripped) and SENSITIVE_NAMES.search(stripped):
            findings.append(Finding("error", "static.secret_logging", "logging statement appears to include a credential, token, cookie, or other sensitive value", location, None, None, {"line": _redact_line(stripped)}))
        if require_correlation and LOG_CALL.search(stripped) and ERROR_WORDS.search(stripped) and not any(field in stripped for field in correlation_fields):
            findings.append(Finding("warning", "static.missing_correlation", "error log may be missing trace/request correlation fields", location, None, None, {"line": _redact_line(stripped), "expected_any": correlation_fields}))
        if detect_unbounded_labels and METRIC_WORDS.search(stripped) and HIGH_CARD_NAMES.search(stripped) and not re.search(r"(?i)(bucket|hash|redact|cardinality|max)", stripped):
            findings.append(Finding("warning", "static.unbounded_label", "metric/tag code appears to use a high-cardinality or user-controlled label without bucketing", location, None, None, {"line": _redact_line(stripped)}))
    return findings


def _redact_line(line: str) -> str:
    line = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", line)
    line = re.sub(r"(?i)((?:password|passwd|pwd|token|secret|authorization|cookie)\s*[:=]\s*)['\"]?[^,'\")\s]+", r"\1<redacted>", line)
    return line[:240]


def _collect_files(paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(child for child in path.rglob("*") if child.suffix in SOURCE_SUFFIXES and child.is_file()))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"source path does not exist: {path}")
    return files
