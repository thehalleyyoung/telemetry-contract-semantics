"""Reduce scanned subjects to a deterministic study dataset and report."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..adapters import load_events_auto
from ..bug_classes import (
    BUG_CLASS_IDS,
    BUG_CLASSES,
    CODE_TO_BUG_CLASS,
    HEADLINE_GAP,
    HEADLINE_QUESTION,
)
from ..loader import ContractLoadError
from ..pipeline import diagnose
from ..repo_scan import (
    RepoScanError,
    find_telemetry_files,
    parse_repo_target,
    scan_directory,
)
from .corpus import CorpusSubject

DATASET_SCHEMA = "telemetry-contracts/corpus-dataset@1"


# ---------------------------------------------------------------------------
# Per-subject reduction
# ---------------------------------------------------------------------------


def subject_record(
    subject: CorpusSubject,
    scan_report: dict[str, Any],
    diagnosis: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reduce one subject's scan + diagnosis to a single flat, sorted study row.

    The row is deterministic given a fixed checkout: every collection is sorted
    and every number is an integer, so the aggregate dataset is byte-stable.
    """

    summary = scan_report.get("summary", {})
    by_code: dict[str, int] = summary.get("by_code", {})

    # Bucket findings into bug classes via the single source of truth.
    bug_class_counts = {gap: 0 for gap in BUG_CLASS_IDS}
    for code, count in by_code.items():
        gap = CODE_TO_BUG_CLASS.get(code)
        if gap is not None:
            bug_class_counts[gap] += int(count)
    bug_class_present = {gap: bug_class_counts[gap] > 0 for gap in BUG_CLASS_IDS}

    has_telemetry = int(summary.get("telemetry_files", 0)) > 0
    score = None
    verdict = None
    failure_events = 0
    if diagnosis is not None:
        score = int(diagnosis["diagnosability_score"])
        verdict = diagnosis["verdict"]
        failure_events = int(diagnosis.get("components", {}).get("failures", 0))
    # The headline question is considered unanswerable only when the
    # conservative, finding-based correlation check fires — the same definition
    # the prevalence table uses — so the headline statistic and the per-class
    # prevalence can never disagree. (This is stricter than diagnose's inline
    # counter, which omits the low-kind-confidence guard that suppresses
    # uncertain findings.)
    headline_blocked = has_telemetry and bug_class_present.get(HEADLINE_GAP, False)

    return {
        "target": subject.target,
        "sha": subject.sha,
        "host": subject.host,
        "license": subject.license,
        "tier": subject.tier,
        "has_telemetry": has_telemetry,
        "event_count": int(summary.get("events", 0)),
        "telemetry_files": int(summary.get("telemetry_files", 0)),
        "candidate_files": int(summary.get("candidate_files", 0)),
        "formats": sorted({f["format"] for f in scan_report.get("files", []) if f.get("format")}),
        "by_kind": dict(sorted(summary.get("by_kind", {}).items())),
        "services": sorted(summary.get("services", [])),
        "diagnosability_score": score,
        "verdict": verdict,
        "failure_events": failure_events,
        "findings_total": int(summary.get("findings", 0)),
        "bug_class_counts": bug_class_counts,
        "bug_class_present": bug_class_present,
        "headline_blocked": headline_blocked,
    }


# ---------------------------------------------------------------------------
# Aggregation (deterministic, integer/fixed-point arithmetic only)
# ---------------------------------------------------------------------------


def _permille(numerator: int, denominator: int) -> int:
    """Return ``1000 * numerator / denominator`` rounded half-up, 0 if denom=0."""

    if denominator <= 0:
        return 0
    return (2000 * numerator + denominator) // (2 * denominator)


def _mean_milli(values: list[int]) -> int:
    """Half-up mean*1000 of a non-empty list (rounding matches ``_permille``)."""

    n = len(values)
    total = sum(values)
    return (2000 * total + n) // (2 * n)


def _nearest_rank(sorted_values: list[int], pct: int) -> int:
    """Nearest-rank percentile of an already-sorted non-empty integer list."""

    n = len(sorted_values)
    # rank = ceil(pct/100 * n), clamped to [1, n]
    rank = (pct * n + 99) // 100
    rank = max(1, min(rank, n))
    return sorted_values[rank - 1]


def _score_distribution(scores: list[int]) -> dict[str, Any]:
    if not scores:
        return {"count": 0}
    s = sorted(scores)
    return {
        "count": len(s),
        "min": s[0],
        "p25": _nearest_rank(s, 25),
        "median": _nearest_rank(s, 50),
        "p75": _nearest_rank(s, 75),
        "max": s[-1],
        "mean_milli": _mean_milli(s),
    }


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine subject rows into the deterministic study dataset.

    Reports, per bug class: how many subjects exhibit it (and the permille), the
    total findings, and a per-host breakdown. Reports the diagnosability-score
    distribution over subjects that have telemetry. Computes the headline
    statistic — the share of telemetry-bearing subjects that cannot answer the
    project's headline incident question — with exact integer arithmetic.
    """

    rows = sorted(records, key=lambda r: (r["target"], r["sha"]))
    n = len(rows)
    with_tel = [r for r in rows if r["has_telemetry"]]
    n_tel = len(with_tel)

    hosts = sorted({r["host"] for r in rows})

    bug_class_prevalence: dict[str, Any] = {}
    for gap in BUG_CLASS_IDS:
        present_rows = [r for r in with_tel if r["bug_class_present"].get(gap)]
        present = len(present_rows)
        per_host = {
            host: sum(1 for r in present_rows if r["host"] == host)
            for host in hosts
        }
        bug_class_prevalence[gap] = {
            "title": BUG_CLASSES[gap]["title"],
            "blocks_question": BUG_CLASSES[gap]["blocks_question"],
            "subjects_present": present,
            "subjects_present_permille": _permille(present, n_tel),
            "total_findings": sum(int(r["bug_class_counts"].get(gap, 0)) for r in with_tel),
            "by_host": {h: c for h, c in sorted(per_host.items()) if c},
        }

    scores = [int(r["diagnosability_score"]) for r in with_tel if r["diagnosability_score"] is not None]

    # Honest denominators: the primary headline is over telemetry-bearing
    # repositories that actually exhibit at least one failure event (a repo with
    # no observed failures vacuously "can answer" and would dilute the claim);
    # the telemetry-bearing denominator is reported alongside for context.
    with_failures = [r for r in with_tel if int(r.get("failure_events", 0)) > 0]
    n_failure = len(with_failures)
    headline_blocked = [r for r in with_tel if r["headline_blocked"]]
    headline = {
        "gap": HEADLINE_GAP,
        "question": HEADLINE_QUESTION,
        "definition": (
            "has at least one sampled failure event that cannot be joined to a "
            "recognized request/trace identifier from telemetry alone"
        ),
        "cannot_answer": len(headline_blocked),
        "denominator": n_failure,
        "denominator_basis": "telemetry-bearing subjects with >=1 failure event",
        "cannot_answer_permille": _permille(len(headline_blocked), n_failure),
        "subjects_with_telemetry": n_tel,
        "share_of_telemetry_permille": _permille(len(headline_blocked), n_tel),
    }

    return {
        "schema": DATASET_SCHEMA,
        "subjects_total": n,
        "subjects_with_telemetry": n_tel,
        "hosts": hosts,
        "events_total": sum(int(r["event_count"]) for r in rows),
        "headline": headline,
        "bug_class_prevalence": bug_class_prevalence,
        "score_distribution": _score_distribution(scores),
        "subjects": rows,
    }


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _fmt_permille(permille: int) -> str:
    """Render a permille integer as a percentage string (e.g. 714 -> '71.4%')."""

    return f"{permille // 10}.{permille % 10}%"


def render_study_markdown(dataset: dict[str, Any]) -> str:
    """Render the aggregate dataset as a deterministic Markdown study report."""

    h = dataset["headline"]
    lines = [
        "# Observability study over pre-existing repositories",
        "",
        f"Subjects analyzed: **{dataset['subjects_total']}** "
        f"({dataset['subjects_with_telemetry']} carry telemetry) "
        f"across hosts: {', '.join(dataset['hosts']) or 'none'}.",
        f"Total telemetry events scanned: {dataset['events_total']}.",
        "",
        "## Headline finding",
        "",
        f"Of the {h['denominator']} telemetry-bearing repositories with at least "
        f"one observed failure event, "
        f"**{h['cannot_answer']} ({_fmt_permille(h['cannot_answer_permille'])})** "
        f"{h['definition']} (i.e. cannot answer: _{h['question']}_).",
        "",
        f"_Caveat: computed over sampled telemetry files/events and recognized "
        f"correlation aliases only; evidence in external traces, unstructured "
        f"messages, or unrecognized fields is not credited._",
        "",
        "## Bug-class prevalence (among telemetry-bearing repositories)",
        "",
        "| Bug class | Repos affected | Share | Findings | Question blocked |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for gap in BUG_CLASS_IDS:
        p = dataset["bug_class_prevalence"][gap]
        lines.append(
            f"| {p['title']} | {p['subjects_present']} | "
            f"{_fmt_permille(p['subjects_present_permille'])} | "
            f"{p['total_findings']} | {p['blocks_question']} |"
        )

    dist = dataset["score_distribution"]
    lines += ["", "## Diagnosability score distribution", ""]
    if dist.get("count"):
        mean = dist["mean_milli"]
        lines += [
            f"Over {dist['count']} telemetry-bearing repositories (0-100, higher is better):",
            "",
            f"- min **{dist['min']}**, p25 **{dist['p25']}**, median **{dist['median']}**, "
            f"p75 **{dist['p75']}**, max **{dist['max']}**",
            f"- mean **{mean // 1000}.{mean % 1000:03d}**",
        ]
    else:
        lines.append("No telemetry-bearing repositories in this corpus.")

    lines += ["", "## Subjects", "", "| Repository | Host | Events | Score | Verdict |",
              "| --- | --- | ---: | ---: | --- |"]
    for r in dataset["subjects"]:
        score = "-" if r["diagnosability_score"] is None else str(r["diagnosability_score"])
        verdict = r["verdict"] or "no telemetry"
        lines.append(f"| {r['target']}@{r['sha'][:12]} | {r['host']} | {r['event_count']} | {score} | {verdict} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Network runner: clone each subject at its pinned SHA and scan it
# ---------------------------------------------------------------------------


def _clone_at_sha(url: str, sha: str, dest: Path, *, timeout: int = 300) -> None:
    """Fetch exactly ``sha`` from ``url`` into ``dest`` (shallow) and check it out.

    Uses ``git init`` + a depth-1 fetch of the specific object, which pins the
    study to an exact commit without downloading full history. Raises
    :class:`RepoScanError` on any git failure.
    """

    if shutil.which("git") is None:
        raise RepoScanError("git is required for corpus mining but was not found on PATH")
    dest.mkdir(parents=True, exist_ok=True)

    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(dest), *args],
            capture_output=True, text=True, timeout=timeout,
        )

    steps = [
        ("init", ["init", "--quiet"]),
        ("remote", ["remote", "add", "origin", url]),
        ("fetch", ["fetch", "--depth", "1", "--quiet", "origin", sha]),
        ("checkout", ["checkout", "--quiet", "FETCH_HEAD"]),
    ]
    for name, args in steps:
        try:
            proc = _git(*args)
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - network dependent
            raise RepoScanError(f"timed out during git {name} for {url}@{sha[:12]}") from exc
        if proc.returncode != 0:
            if name == "fetch":
                # Some servers refuse direct fetch-by-SHA; fall back to a full
                # (no-checkout) clone and check the exact commit out.
                _full_clone_at_sha(url, sha, dest, timeout=timeout)
                return
            detail = (proc.stderr or "").strip().splitlines()
            message = detail[-1] if detail else f"exit {proc.returncode}"
            raise RepoScanError(f"git {name} failed for {url}@{sha[:12]}: {message}")


def _full_clone_at_sha(url: str, sha: str, dest: Path, *, timeout: int = 300) -> None:
    """Fallback: full clone (no checkout) then checkout the exact ``sha``."""

    shutil.rmtree(dest, ignore_errors=True)
    try:
        clone = subprocess.run(
            ["git", "clone", "--no-checkout", "--quiet", url, str(dest)],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - network dependent
        raise RepoScanError(f"timed out cloning {url}") from exc
    if clone.returncode != 0:
        detail = (clone.stderr or "").strip().splitlines()
        raise RepoScanError(
            f"git clone failed for {url}: {detail[-1] if detail else clone.returncode}"
        )
    checkout = subprocess.run(
        ["git", "-C", str(dest), "checkout", "--quiet", sha],
        capture_output=True, text=True, timeout=timeout,
    )
    if checkout.returncode != 0:
        detail = (checkout.stderr or "").strip().splitlines()
        raise RepoScanError(
            f"git checkout {sha[:12]} failed for {url}: "
            f"{detail[-1] if detail else checkout.returncode}"
        )


def _repo_diagnosis(
    root: Path,
    *,
    max_total_events: int,
    max_events_per_file: int,
    service: str | None,
    max_files: int = 300,
    max_file_bytes: int = 25_000_000,
) -> dict[str, Any] | None:
    """Diagnose the union of telemetry events under ``root`` (deterministic).

    Uses the *same* ``max_files``/``max_file_bytes`` discovery bounds as the
    accompanying ``scan_directory`` call so the diagnosability score and the
    finding-based bug-class presence are always computed over the same set of
    telemetry files.
    """

    union: list[dict[str, Any]] = []
    for path in find_telemetry_files(root, max_files=max_files, max_file_bytes=max_file_bytes):
        if len(union) >= max_total_events:
            break
        try:
            loaded = load_events_auto(path, tolerant=True)
        except (ContractLoadError, ValueError, OSError):
            continue
        events = loaded["events"][:max_events_per_file]
        union.extend(events[: max_total_events - len(union)])
    if not union:
        return None
    return diagnose(union, service=service)


def mine_corpus(
    subjects: list[CorpusSubject],
    *,
    service: str | None = None,
    max_files: int = 300,
    max_events_per_file: int = 50_000,
    max_total_events: int = 200_000,
    on_subject: Any = None,
) -> dict[str, Any]:
    """Clone each subject at its pinned SHA, scan it, and aggregate the results.

    Network-bound. Each subject is cloned into a fresh temp dir that is removed
    immediately after scanning, so disk use stays bounded regardless of corpus
    size. Subjects that fail to clone/scan are recorded as errors (the study
    continues) rather than aborting the whole run.
    """

    records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for subject in subjects:
        tmp = tempfile.mkdtemp(prefix="telemetry-contracts-mine-")
        try:
            clone_dir = Path(tmp) / "repo"
            _clone_at_sha(parse_repo_target(subject.target), subject.sha, clone_dir)
            scan_report = scan_directory(
                clone_dir, service=service,
                max_files=max_files, max_events_per_file=max_events_per_file,
            )
            diagnosis = _repo_diagnosis(
                clone_dir, max_total_events=max_total_events,
                max_events_per_file=max_events_per_file, service=service,
                max_files=max_files,
            )
            record = subject_record(subject, scan_report, diagnosis)
            records.append(record)
            if on_subject is not None:
                on_subject(subject, record, None)
        except RepoScanError as exc:
            err = {"target": subject.target, "sha": subject.sha, "error": str(exc)}
            errors.append(err)
            if on_subject is not None:
                on_subject(subject, None, str(exc))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    dataset = aggregate(records)
    dataset["errors"] = sorted(errors, key=lambda e: (e["target"], e["sha"]))
    return dataset
