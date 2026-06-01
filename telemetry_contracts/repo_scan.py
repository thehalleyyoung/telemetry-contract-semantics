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

import os
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

# Host shorthands: ``<host-prefix>owner/repo`` -> ``https://<host>/owner/repo.git``.
# Order matters only in that the longest/most-specific prefixes are distinct.
_HOST_PREFIXES = {
    "github.com/": "github.com",
    "gitlab.com/": "gitlab.com",
    "bitbucket.org/": "bitbucket.org",
    "codeberg.org/": "codeberg.org",
    "gh:": "github.com",
    "gl:": "gitlab.com",
    "bb:": "bitbucket.org",
}


def parse_repo_target(target: str) -> str:
    """Return a safe clone URL for ``owner/repo`` shorthand or a full git URL.

    Recognized forms:
      * a full ``https://``/``git@``/``ssh://``/``git://`` URL (any host) -> used as-is;
      * ``owner/repo`` -> defaults to GitHub;
      * ``<host>/owner/repo`` for github.com, gitlab.com, bitbucket.org, codeberg.org;
      * ``gh:``/``gl:``/``bb:`` prefixes for github/gitlab/bitbucket.
    """

    target = target.strip()
    if _GIT_URL.match(target):
        return target
    host = "github.com"
    for prefix, prefix_host in _HOST_PREFIXES.items():
        if target.startswith(prefix):
            target = target[len(prefix):]
            host = prefix_host
            break
    if _REPO_SHORTHAND.match(target):
        owner_repo = target[:-4] if target.endswith(".git") else target
        return f"https://{host}/{owner_repo}.git"
    raise RepoScanError(
        f"unrecognized repository target '{target}'; use 'owner/repo', "
        "'<host>/owner/repo', or a full https/git URL"
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
    deep: bool = False,
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
            deep=deep,
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
    deep: bool = False,
    max_total_events: int = 200_000,
) -> dict[str, Any]:
    """Discover and analyze telemetry files under ``root`` (no contract needed).

    When ``deep`` is true, also infer per-service execution semantics (a draft
    contract, its small-step derivation, and an observed execution order) and an
    informational runtime/source alignment — turning observability into a
    checkable correctness property for whatever data the project already ships.
    """

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
    deep_events: list[dict[str, Any]] = []

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
        if deep and len(deep_events) < max_total_events:
            deep_events.extend(events[: max_total_events - len(deep_events)])
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

    result = {
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

    if deep:
        result["semantics"] = _deep_semantics(deep_events, root_path, service=service)

    return result


def _deep_semantics(
    events: list[dict[str, Any]], root_path: Path, *, service: str | None
) -> dict[str, Any]:
    """Per-service inferred execution semantics + source alignment (deep scan)."""

    from .project_semantics import (
        align_runtime_with_source,
        find_source_files,
        group_events_by_service,
        infer_execution_semantics,
        semantics_summary,
    )

    grouped = group_events_by_service(events)
    if service is not None:
        grouped = {name: evs for name, evs in grouped.items() if name == service}
    source_files = find_source_files(str(root_path))

    per_service: list[dict[str, Any]] = []
    alignment: list[dict[str, Any]] = []
    for name in sorted(grouped):
        svc_events = grouped[name]
        report = infer_execution_semantics(
            svc_events,
            service=None if name == "(unspecified)" else name,
            infer_sequences=True,
        )
        per_service.append(semantics_summary(report))
        align = align_runtime_with_source(report["inferred_contract"], source_files)
        align["service"] = name
        alignment.append(align)

    return {
        "services": per_service,
        "source_alignment": alignment,
        "source_files": len(source_files),
    }


def find_telemetry_files(
    root: Path,
    *,
    max_files: int = 300,
    max_file_bytes: int = 25_000_000,
    max_entries: int = 200_000,
) -> list[Path]:
    """Return candidate telemetry files under ``root`` in deterministic order.

    Uses a pruned, bounded walk: vendored/build/VCS directories are skipped
    *before* descending into them, and the walk stops after ``max_entries``
    filesystem entries so pointing the scanner at a huge tree (or a home
    directory) stays responsive instead of materializing the whole tree.
    """

    candidates: list[Path] = []
    examined = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip dirs in place so os.walk never descends into them.
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            examined += 1
            if examined > max_entries:
                break
            path = Path(dirpath) / name
            if not _is_candidate(path, root):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size == 0 or size > max_file_bytes:
                continue
            candidates.append(path)
        if examined > max_entries:
            break
    candidates.sort()
    return candidates[:max_files]


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


_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}


def _severity_rank(severity: str) -> int:
    return _SEVERITY_RANK.get(severity, 3)


def _sorted_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Errors first, then a deterministic secondary order, without mutating input."""

    indexed = list(enumerate(findings))
    indexed.sort(
        key=lambda pair: (
            _severity_rank(pair[1].get("severity", "")),
            pair[1].get("code", ""),
            pair[1].get("source_file", ""),
            pair[1].get("path", ""),
            pair[0],
        )
    )
    return [item for _, item in indexed]


def _code_severity_map(findings: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for finding in findings:
        code = finding.get("code", "")
        sev = finding.get("severity", "")
        # keep the most severe seen for a code
        if code not in mapping or _severity_rank(sev) < _severity_rank(mapping[code]):
            mapping[code] = sev
    return mapping


def _top_issue_lines(report: dict[str, Any]) -> list[str]:
    by_code = report["summary"].get("by_code", {})
    if not by_code:
        return []
    sev_map = _code_severity_map(report["findings"])
    ranked = sorted(
        by_code.items(),
        key=lambda kv: (_severity_rank(sev_map.get(kv[0], "info")), -kv[1], kv[0]),
    )
    width = max(len(code) for code, _ in ranked)
    lines = ["", "Top issue types:"]
    for code, count in ranked:
        sev = sev_map.get(code, "info")
        lines.append(f"  {sev:<7} {code:<{width}}  {count}")
    return lines


def _top_code(report: dict[str, Any]) -> str | None:
    by_code = report["summary"].get("by_code", {})
    if not by_code:
        return None
    sev_map = _code_severity_map(report["findings"])
    ranked = sorted(by_code.items(), key=lambda kv: (_severity_rank(sev_map.get(kv[0], "info")), -kv[1], kv[0]))
    return ranked[0][0]


def _scan_next_steps(report: dict[str, Any]) -> list[str]:
    summary = report["summary"]
    cli = "python3 -m telemetry_contracts.cli"
    lines = ["", "Next steps:"]
    if summary["telemetry_files"] == 0:
        lines.append(f"  - Point the scanner at the folder that holds your logs: {cli} scan --path ./logs")
        lines.append(f"  - Or analyze a single log file directly:               {cli} analyze --events your-logs.jsonl")
        return lines
    example_file = report["files"][0]["path"]
    if report["findings"]:
        code = _top_code(report) or "<code>"
        lines.append(f"  - Understand a finding:        {cli} explain {code}")
        lines.append(f"  - Inspect one file:            {cli} analyze --events {example_file} --format markdown")
        lines.append(f"  - Lock it in (draft contract): {cli} infer-contract --events {example_file} > telemetry-contract.json")
    else:
        lines.append("  - Looks clean. Bootstrap a starter contract to keep it that way:")
        lines.append(f"      {cli} infer-contract --events {example_file} > telemetry-contract.json")
    return lines


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
        lines.append("**Next steps**")
        lines.append("")
        lines.append("- Point the scanner at the folder that holds your logs: `scan --path ./logs`")
        lines.append("- Or analyze a single log file directly: `analyze --events your-logs.jsonl`")
        lines.append("")
        return "\n".join(lines)
    by_code = summary.get("by_code", {})
    if by_code:
        sev_map = _code_severity_map(report["findings"])
        ranked = sorted(by_code.items(), key=lambda kv: (_severity_rank(sev_map.get(kv[0], "info")), -kv[1], kv[0]))
        lines.extend(["## Top issue types", "", "| Severity | Code | Count |", "| --- | --- | ---: |"])
        for code, count in ranked:
            lines.append(f"| {sev_map.get(code, 'info')} | `{code}` | {count} |")
        lines.append("")
    lines.extend(["## Files", "", "| File | Format | Events | Findings |", "| --- | --- | ---: | ---: |"])
    for file in report["files"]:
        lines.append(f"| `{file['path']}` | {file['format']} | {file['events']} | {file['findings']} |")
    lines.append("")
    if report["findings"]:
        lines.extend(["## Findings (most severe first)", "", "| Severity | Code | File | Message |", "| --- | --- | --- | --- |"])
        for finding in _sorted_findings(report["findings"])[:200]:
            lines.append(f"| {finding['severity']} | `{finding['code']}` | `{finding.get('source_file', '')}` | {finding['message']} |")
        lines.append("")
    example_file = report["files"][0]["path"]
    if report.get("semantics"):
        lines.extend(_format_deep_semantics_markdown(report["semantics"]))
    lines.extend(["## Next steps", ""])
    if report["findings"]:
        lines.append(f"- Understand a finding: `explain <code>`")
        lines.append(f"- Inspect one file: `analyze --events {example_file} --format markdown`")
        lines.append(f"- Draft a contract from it: `infer-contract --events {example_file}`")
    else:
        lines.append(f"- Looks clean. Bootstrap a starter contract: `infer-contract --events {example_file}`")
    lines.append("")
    return "\n".join(lines)


def format_scan_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    where = report["repo"]["url"] if report.get("repo") else report["root"]
    lines = [
        f"Scanned {where}: {summary['telemetry_files']} telemetry file(s), {summary['events']} event(s), {summary['findings']} finding(s) "
        f"({summary['by_severity']['error']} error, {summary['by_severity']['warning']} warning).",
    ]
    if summary["telemetry_files"] == 0:
        lines.append("No telemetry/log data files were discovered in this project.")
        lines.extend(_scan_next_steps(report))
        return "\n".join(lines)
    lines.extend(_top_issue_lines(report))
    lines.append("")
    lines.append("Findings (most severe first):")
    shown = _sorted_findings(report["findings"])[:200]
    for finding in shown:
        lines.append(
            f"  {finding['severity'].upper()} {finding['code']} in {finding.get('source_file', '')}"
            f" at {finding.get('path', '')}: {finding['message']}"
        )
    if summary["findings"] > len(shown):
        lines.append(f"  ... and {summary['findings'] - len(shown)} more (showing first 200)")
    if report.get("semantics"):
        lines.extend(_format_deep_semantics_text(report["semantics"]))
    lines.extend(_scan_next_steps(report))
    return "\n".join(lines)


def _format_deep_semantics_text(semantics: dict[str, Any]) -> list[str]:
    lines = ["", "Execution semantics (inferred per service):"]
    for entry in semantics.get("services", []):
        name = entry.get("service") or "(unspecified)"
        verdict = "consistent" if entry["pass"] else "inconsistent"
        aligned = "aligned" if entry["aligned_with_checker"] else "diverged"
        lines.append(
            f"  {name}: {entry['small_steps']} small steps over {entry['relevant_events']} events"
            f" -> {verdict} ({aligned} with checker)"
        )
        order = entry.get("inferred_ordering")
        if order:
            chain = " -> ".join(order["steps"])
            status = "enforceable" if order["enforceable"] else "candidate"
            lines.append(
                f"    order [{order['correlation_key']}]: {chain}"
                f"  ({status}; {order['support_full_groups']} groups, {order['partial_groups']} partial)"
            )
    for align in semantics.get("source_alignment", []):
        name = align.get("service") or "(unspecified)"
        if not align.get("expected_signals"):
            continue
        located = len(align.get("located_in_source", []))
        missing = len(align.get("not_located_in_source", []))
        lines.append(
            f"  {name}: {located}/{align['expected_signals']} runtime signal name(s) located in source"
            f" ({missing} not located; informational)"
        )
    return lines


def _format_deep_semantics_markdown(semantics: dict[str, Any]) -> list[str]:
    lines = ["## Execution semantics (inferred per service)", ""]
    for entry in semantics.get("services", []):
        name = entry.get("service") or "(unspecified)"
        verdict = "consistent" if entry["pass"] else "inconsistent"
        aligned = "aligned" if entry["aligned_with_checker"] else "diverged"
        lines.append(
            f"- **`{name}`** — {entry['small_steps']} small steps over "
            f"{entry['relevant_events']} events → **{verdict}** ({aligned} with checker)"
        )
        order = entry.get("inferred_ordering")
        if order:
            chain = " → ".join(f"`{step}`" for step in order["steps"])
            status = "enforceable" if order["enforceable"] else "candidate"
            lines.append(
                f"  - order (`{order['correlation_key']}`): {chain} "
                f"— _{status}; {order['support_full_groups']} groups, {order['partial_groups']} partial_"
            )
    has_alignment = any(a.get("expected_signals") for a in semantics.get("source_alignment", []))
    if has_alignment:
        lines.append("")
        lines.append("Runtime/source alignment (informational — names often differ):")
        lines.append("")
        for align in semantics.get("source_alignment", []):
            if not align.get("expected_signals"):
                continue
            name = align.get("service") or "(unspecified)"
            located = len(align.get("located_in_source", []))
            missing = len(align.get("not_located_in_source", []))
            lines.append(
                f"- `{name}`: {located}/{align['expected_signals']} located in source "
                f"({missing} not located)"
            )
    lines.append("")
    return lines
