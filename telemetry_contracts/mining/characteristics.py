"""Cheap, deterministic repository characteristics for correlation (pure stdlib).

The mining study can break gap prevalence down by simple characteristics that are
*already available* from a checkout, without any extra tooling:

* **Primary language** — inferred from source-file extension counts.
* **Instrumentation library present/absent** — inferred by scanning well-known
  dependency manifests for known logging/telemetry libraries.
* **Event volume** — already carried on each study row (``event_count``).

Everything here is bounded (file count and per-file byte budgets) and fully
deterministic: extension maps and library tokens are fixed constants and all
outputs are sorted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Source-file extension -> language label. Fixed and sorted-stable.
_EXT_LANGUAGE: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rb": "Ruby",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rs": "Rust",
    ".php": "PHP",
    ".cs": "C#",
    ".scala": "Scala",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".ex": "Elixir",
    ".exs": "Elixir",
}

# Dependency-manifest filename -> known telemetry/logging library tokens to look
# for (substring match, case-insensitive). Tokens are intentionally conservative.
_MANIFEST_TOKENS: dict[str, tuple[str, ...]] = {
    "requirements.txt": ("opentelemetry", "structlog", "loguru", "python-json-logger", "ddtrace", "sentry-sdk", "prometheus-client"),
    "pyproject.toml": ("opentelemetry", "structlog", "loguru", "python-json-logger", "ddtrace", "sentry-sdk", "prometheus-client"),
    "setup.py": ("opentelemetry", "structlog", "loguru", "ddtrace", "sentry-sdk", "prometheus-client"),
    "Pipfile": ("opentelemetry", "structlog", "loguru", "ddtrace", "sentry-sdk"),
    "package.json": ("@opentelemetry", "winston", "pino", "bunyan", "@sentry", "dd-trace", "prom-client", "log4js"),
    "go.mod": ("go.opentelemetry.io", "uber.org/zap", "sirupsen/logrus", "rs/zerolog", "DataDog/dd-trace-go", "getsentry/sentry-go"),
    "Gemfile": ("opentelemetry", "lograge", "semantic_logger", "ddtrace", "sentry-ruby"),
    "pom.xml": ("opentelemetry", "logback", "log4j", "io.sentry", "datadog"),
    "build.gradle": ("opentelemetry", "logback", "log4j", "io.sentry", "datadog"),
    "Cargo.toml": ("opentelemetry", "tracing", "slog", "log4rs", "sentry"),
}

_MAX_MANIFEST_BYTES = 2_000_000


def detect_language(root: Path, *, max_files: int = 5000) -> dict[str, Any]:
    """Return ``{"language": <primary or None>, "counts": {lang: n, ...}}``.

    Counts source files by extension; ties are broken by language name so the
    primary language is deterministic.
    """

    counts: dict[str, int] = {}
    seen = 0
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if seen >= max_files:
            break
        if not path.is_file():
            continue
        parts = set(path.parts)
        if "__pycache__" in parts or ".git" in parts or "node_modules" in parts:
            continue
        lang = _EXT_LANGUAGE.get(path.suffix.lower())
        if lang is None:
            continue
        counts[lang] = counts.get(lang, 0) + 1
        seen += 1
    if not counts:
        return {"language": None, "counts": {}}
    # Primary = most files, ties broken by language name (deterministic).
    primary = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return {"language": primary, "counts": dict(sorted(counts.items()))}


def detect_instrumentation(root: Path) -> dict[str, Any]:
    """Detect known telemetry/logging libraries from dependency manifests."""

    found: set[str] = set()
    for manifest, tokens in _MANIFEST_TOKENS.items():
        for path in sorted(root.rglob(manifest), key=lambda p: p.as_posix()):
            parts = set(path.parts)
            if ".git" in parts or "node_modules" in parts:
                continue
            try:
                if path.stat().st_size > _MAX_MANIFEST_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            for token in tokens:
                if token.lower() in text:
                    found.add(token)
    return {
        "instrumentation_present": bool(found),
        "instrumentation_libraries": sorted(found),
    }


def detect_characteristics(root: Path, *, max_files: int = 5000) -> dict[str, Any]:
    """Combine language + instrumentation detection into one sorted dict."""

    language = detect_language(root, max_files=max_files)
    instrumentation = detect_instrumentation(root)
    return {
        "language": language["language"],
        "language_counts": language["counts"],
        "instrumentation_present": instrumentation["instrumentation_present"],
        "instrumentation_libraries": instrumentation["instrumentation_libraries"],
    }
