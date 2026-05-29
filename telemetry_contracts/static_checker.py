from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .findings import Finding


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
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in files)
    findings: list[Finding] = []
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for name in expected_names(contract)[section]:
            if name not in corpus:
                findings.append(Finding("error", "static.missing_instrumentation", f"expected {kind} name '{name}' was not found in source literals", "source", f"$.static_expectations.{section}", None, {"name": name}))
    if not files:
        findings.append(Finding("warning", "static.no_sources", "no source files were checked", "source"))
    return findings


def _collect_files(paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(child for child in path.rglob("*") if child.suffix in {".py", ".js", ".ts", ".go", ".java", ".cs", ".rb"} and child.is_file()))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"source path does not exist: {path}")
    return files
