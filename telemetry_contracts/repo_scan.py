"""Scan an arbitrary project (local directory or GitHub repository) for telemetry.

This extends the "use it now with the data you already have" idea from a single
file to a whole project: point it at any GitHub repo and it will discover the
telemetry/log files that project already ships — in whatever format — load them
best-effort, and run the contract-free :func:`analyze_events` checks over them.

No contract, no relabeling, no instrumentation changes required. Cloning uses a
shallow ``git clone`` of the requested ref; discovery is heuristic and skips
configuration files, lockfiles, and vendored/build directories.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .adapters import load_events_auto
from .discover import analyze_events
from .loader import ContractLoadError


class RepoScanError(ValueError):
    """Raised when a repository cannot be fetched or scanned."""


# Directories that never contain a project's own telemetry and are expensive to walk.
_SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "bower_components", "dist",
    "build", "out", "target", ".venv", "venv", "env", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".tox", ".idea", ".vscode", "site-packages", ".next", ".cache",
    "coverage", ".gradle",
}
# Extensions we always treat as candidate telemetry.
_LOG_EXTENSIONS = {".jsonl", ".ndjson", ".log", ".logfmt"}
# .json is only a candidate when the path hints at telemetry (otherwise it is
# almost always config/lockfile/manifest data).
_TELEMETRY_HINTS = (
    "log", "logs", "telemetry", "trace", "traces", "span", "spans", "metric",
    "metrics", "otlp", "event", "events", "audit", "jsonl", "fixtures",
    "fixture", "testdata", "sample", "samples", "observability",
)
_EXCLUDE_JSON_NAMES = {
    "package.json", "package-lock.json", "composer.json", "composer.lock",
    "manifest.json", "angular.json", "renovate.json", "now.json", "vercel.json",
    "babel.config.json", "jest.config.json", "components.json", "deno.json",
    "bun.lockb", "biome.json", "turbo.json", "nx.json", "lerna.json",
}
_EXCLUDE_JSON_PATTERNS = (
    re.compile(r"(?i)tsconfig.*\.json$"),
    re.compile(r"(?i).*\.config\.json$"),
    re.compile(r"(?i)^\..*rc\.json$"),
    re.compile(r"(?i).*schema.*\.json$"),
)

_REPO_SHORTHAND = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GIT_URL = re.compile(r"^(https?://|git@|ssh://|git://)[\w./:@%+~-]+$")


def parse_repo_target(target: str) -> str:
    """Return a safe clone URL for ``owner/repo`` shorthand or a full git URL."""

    target = target.strip()
    if _GIT_URL.match(target):
        return target
    if target.startswith("github.com/"):
        target = target[len("github.com/"):]
    if _REPO_SHORTHAND.match(target):
        owner_repo = target[:-4] if target.endswith(".git") else target
        return f"https://github.com/{owner_repo}.git"
    raise RepoScanError(
        f"unrecognized repository target '{target}'; use 'owner/repo' or a full https/git URL"
    )


def clone_repo(target: str, dest: str | Path, *, ref: str | None = None, depth: int = 1) -> dict[str, Any]:
    """Shallow-clone ``target`` into ``dest`` and return clone metadata."""

    if shutil.which("git") is None:
        raise RepoScanError("git is required to clone repositories but was not found on PATH")
    url = parse_repo_target(target)
    dest_path = Path(dest)
    command = ["git", "clone", "--depth", str(depth), "--quiet"]
    if ref:
        command += ["--branch", ref]
    command += [url, str(dest_path)]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - network dependent
        raise RepoScanError(f"timed out cloning {url}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        message = detail[-1] if detail else f"exit code {exc.returncode}"
        raise RepoScanError(f"failed to clone {url}: {message}") from exc
    return {"target": target, "url": url, "ref": ref, "path": str(dest_path)}


def scan_repo(
    target: str,
    *,
    ref: str | None = None,
    service: str | None = None,
    max_files: int = 300,
    max_file_bytes: int = 25_000_000,
    max_events_per_file: int = 50_000,
) -> dict[str, Any]:
    """Clone ``target`` into a temporary directory and scan it for telemetry."""

    tmp = tempfile.mkdtemp(prefix="telemetry-contracts-scan-")
    try:
        clone_dir = Path(tmp) / "repo"
        clone = clone_repo(target, clone_dir, ref=ref)
        report = scan_directory(
            clone_dir,
            service=service,
            max_files=max_files,
            max_file_bytes=max_file_bytes,
            max_events_per_file=max_events_per_file,
        )
        report["repo"] = clone
        report["root"] = target
        return report
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def scan_directory(
    root: str | Path,
    *,
    service: str | None = None,
    max_files: int = 300,
    max_file_bytes: int = 25_000_000,
    max_events_per_file: int = 50_000,
) -> dict[str, Any]:
    """Discover and analyze telemetry files under ``root`` (no contract needed)."""

    root_path = Path(root)
    if not root_path.exists():
        raise RepoScanError(f"path does not exist: {root_path}")

    candidates = find_telemetry_files(root_path, max_files=max_files, max_file_bytes=max_file_bytes)
    scanned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    by_kind: dict[str, int] = {}
    services: set[str] = set()
    total_events = 0

    for path in candidates:
        rel = str(path.relative_to(root_path))
        try:
            loaded = load_events_auto(path, tolerant=True)
        except (ContractLoadError, ValueError, OSError) as exc:
            skipped.append({"path": rel, "reason": str(exc)})
            continue
        events = loaded["events"][:max_events_per_file]
        if not events:
            skipped.append({"path": rel, "reason": "no telemetry records parsed"})
            continue
        report = analyze_events(events, service=service)
        for finding in report["findings"]:
            finding["source_file"] = rel
            all_findings.append(finding)
        summary = loaded.get("summary", {})
        for kind, count in summary.get("by_kind", {}).items():
            by_kind[kind] = by_kind.get(kind, 0) + count
        services.update(summary.get("services", []))
        total_events += len(events)
        scanned.append(
            {
                "path": rel,
                "format": loaded.get("format"),
                "events": len(events),
                "findings": report["summary"]["findings"],
                "parse_diagnostics": len(loaded.get("diagnostics", [])),
            }
        )

    by_severity = {"error": 0, "warning": 0, "info": 0}
    by_code: dict[str, int] = {}
    for finding in all_findings:
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
        by_code[finding["code"]] = by_code.get(finding["code"], 0) + 1

    return {
        "schema": "telemetry-contracts/repo-scan@1",
        "root": str(root_path),
        "repo": None,
        "summary": {
            "telemetry_files": len(scanned),
            "candidate_files": len(candidates),
            "skipped_files": len(skipped),
            "events": total_events,
            "by_kind": dict(sorted(by_kind.items())),
            "services": sorted(services),
            "findings": len(all_findings),
            "by_severity": by_severity,
            "by_code": dict(sorted(by_code.items())),
        },
        "files": scanned,
        "skipped": skipped,
        "findings": all_findings,
    }


def find_telemetry_files(root: Path, *, max_files: int = 300, max_file_bytes: int = 25_000_000) -> list[Path]:
    """Return candidate telemetry files under ``root`` in deterministic order."""

    candidates: list[Path] = []
    for path in sorted(root.rglob("*")):
        if len(candidates) >= max_files:
            break
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if not _is_candidate(path, root):
            continue
        try:
            if path.stat().st_size > max_file_bytes or path.stat().st_size == 0:
                continue
        except OSError:
            continue
        candidates.append(path)
    return candidates


def _is_candidate(path: Path, root: Path) -> bool:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in _LOG_EXTENSIONS:
        return True
    if suffix == ".json":
        if name in _EXCLUDE_JSON_NAMES:
            return False
        if any(pattern.search(name) for pattern in _EXCLUDE_JSON_PATTERNS):
            return False
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            rel_parts = path.parts
        hint_haystack = "/".join(part.lower() for part in rel_parts)
        return any(hint in hint_haystack for hint in _TELEMETRY_HINTS)
    return False


def format_scan_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = ["# Telemetry scan report", ""]
    if report.get("repo"):
        lines.append(f"Repository: `{report['repo']['url']}`" + (f" @ `{report['repo']['ref']}`" if report['repo'].get('ref') else ""))
    else:
        lines.append(f"Path: `{report['root']}`")
    lines.extend(
        [
            "",
            f"- Telemetry files found: **{summary['telemetry_files']}** (of {summary['candidate_files']} candidates; {summary['skipped_files']} skipped)",
            f"- Events analyzed: **{summary['events']}**",
            f"- Services seen: {', '.join(f'`{s}`' for s in summary['services']) or 'n/a'}",
            f"- Findings: **{summary['findings']}** ({summary['by_severity']['error']} error, {summary['by_severity']['warning']} warning)",
            "",
        ]
    )
    if summary["telemetry_files"] == 0:
        lines.append("No telemetry/log data files were discovered in this project.")
        lines.append("")
        return "\n".join(lines)
    lines.extend(["## Files", "", "| File | Format | Events | Findings |", "| --- | --- | ---: | ---: |"])
    for file in report["files"]:
        lines.append(f"| `{file['path']}` | {file['format']} | {file['events']} | {file['findings']} |")
    lines.append("")
    if report["findings"]:
        lines.extend(["## Findings", "", "| Severity | Code | File | Message |", "| --- | --- | --- | --- |"])
        for finding in report["findings"][:200]:
            lines.append(f"| {finding['severity']} | `{finding['code']}` | `{finding.get('source_file', '')}` | {finding['message']} |")
        lines.append("")
    return "\n".join(lines)


def format_scan_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    where = report["repo"]["url"] if report.get("repo") else report["root"]
    lines = [
        f"Scanned {where}: {summary['telemetry_files']} telemetry file(s), {summary['events']} event(s), {summary['findings']} finding(s).",
    ]
    if summary["telemetry_files"] == 0:
        lines.append("No telemetry/log data files were discovered in this project.")
        return "\n".join(lines)
    for finding in report["findings"][:200]:
        lines.append(f"{finding['severity'].upper()} {finding['code']} in {finding.get('source_file', '')} at {finding.get('path', '')}: {finding['message']}")
    if summary["findings"] > min(200, summary["findings"]):
        lines.append(f"... and more (showing first 200)")
    return "\n".join(lines)
