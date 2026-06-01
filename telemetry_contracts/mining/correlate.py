"""Correlate gap prevalence with simple repository characteristics (pure stdlib).

Given the per-subject rows produced by :func:`telemetry_contracts.mining.study.aggregate`,
break the headline gap down by characteristics that are already available on each
row — primary language, whether a telemetry/instrumentation library is declared,
and event volume — so the study can report *where* observability gaps cluster.

All arithmetic is exact integer / fixed-point and every grouping is sorted, so the
breakdown is byte-deterministic.
"""

from __future__ import annotations

from typing import Any

# Fixed, sorted event-volume buckets: (label, lower_inclusive, upper_inclusive).
_VOLUME_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("0", 0, 0),
    ("1-99", 1, 99),
    ("100-999", 100, 999),
    ("1k-9999", 1000, 9999),
    ("10k+", 10000, 1 << 62),
)


def _permille(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return (numerator * 1000 + denominator // 2) // denominator


def _mean_milli(values: list[int]) -> int | None:
    if not values:
        return None
    return (sum(values) * 1000 + len(values) // 2) // len(values)


def _volume_label(event_count: int) -> str:
    for label, low, high in _VOLUME_BUCKETS:
        if low <= event_count <= high:
            return label
    return _VOLUME_BUCKETS[-1][0]


def _group_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic gap/score statistics for one group of subject rows."""

    with_tel = [r for r in rows if r.get("has_telemetry")]
    with_failures = [r for r in with_tel if int(r.get("failure_events", 0)) > 0]
    blocked = [r for r in with_tel if r.get("headline_blocked")]
    scores = [
        int(r["diagnosability_score"])
        for r in with_tel
        if r.get("diagnosability_score") is not None
    ]
    return {
        "subjects": len(rows),
        "with_telemetry": len(with_tel),
        "with_failures": len(with_failures),
        "cannot_answer": len(blocked),
        "cannot_answer_permille": _permille(len(blocked), len(with_failures)),
        "mean_score_milli": _mean_milli(scores),
    }


def _breakdown(rows: list[dict[str, Any]], key: Any) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        label = key(row)
        groups.setdefault(label, []).append(row)
    return {label: _group_stats(groups[label]) for label in sorted(groups)}


def correlate(dataset_or_rows: Any) -> dict[str, Any]:
    """Return gap/score breakdowns by language, instrumentation, and volume.

    Accepts either a full aggregate dataset (uses its ``subjects`` rows) or a
    bare list of subject rows.
    """

    if isinstance(dataset_or_rows, dict):
        rows = list(dataset_or_rows.get("subjects", []))
    else:
        rows = list(dataset_or_rows)

    by_language = _breakdown(rows, lambda r: r.get("language") or "unknown")
    by_instrumentation = _breakdown(
        rows,
        lambda r: "present" if r.get("instrumentation_present") else "absent",
    )
    by_volume = _breakdown(rows, lambda r: _volume_label(int(r.get("event_count", 0))))

    return {
        "schema": "telemetry-contracts/corpus-correlation@1",
        "subjects_total": len(rows),
        "by_language": by_language,
        "by_instrumentation": by_instrumentation,
        "by_event_volume": by_volume,
    }


def _fmt_permille(permille: int) -> str:
    return f"{permille // 10}.{permille % 10}%"


def _fmt_score(mean_milli: int | None) -> str:
    if mean_milli is None:
        return "n/a"
    return f"{mean_milli // 1000}.{(mean_milli % 1000) // 100}"


def render_correlation_markdown(correlation: dict[str, Any]) -> str:
    """Render the correlation breakdown as deterministic Markdown."""

    lines = [
        "# Gap prevalence by repository characteristic",
        "",
        f"Subjects: **{correlation['subjects_total']}**.",
        "",
    ]
    sections = [
        ("By primary language", "by_language"),
        ("By instrumentation library", "by_instrumentation"),
        ("By event volume", "by_event_volume"),
    ]
    for title, key in sections:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Group | Subjects | With telemetry | With failures | Cannot answer | Share | Mean score |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for label, stats in correlation[key].items():
            lines.append(
                f"| {label} | {stats['subjects']} | {stats['with_telemetry']} | "
                f"{stats['with_failures']} | {stats['cannot_answer']} | "
                f"{_fmt_permille(stats['cannot_answer_permille'])} | "
                f"{_fmt_score(stats['mean_score_milli'])} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
