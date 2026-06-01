"""Gold-set schema, parser, and validator for the precision/recall benchmark.

A gold set is a JSONL file: one labeled *sample* per line. Each sample pairs a
small list of telemetry events with a target bug class and a boolean gold label
(``true`` = the bug class is genuinely present in the sample, ``false`` = it is
genuinely absent), plus a short human rationale and optional provenance.

The unit of evaluation is a *(sample, bug-class)* pair. Keeping samples small
and explicit makes every label objectively checkable and the benchmark fully
reproducible: the same gold file always yields the same metrics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..bug_classes import BUG_CLASS_IDS

GOLD_SCHEMA = "telemetry-contracts/gold@1"

_BUG_CLASS_SET = set(BUG_CLASS_IDS)


class GroundTruthError(ValueError):
    """Raised when a gold set is malformed."""


@dataclass(frozen=True)
class GoldItem:
    """One hand-labeled sample.

    Attributes:
        id: stable, unique identifier for the sample.
        bug_class: the bug class this sample is labeled for.
        label: ``True`` iff the bug class is genuinely present (positive).
        events: the telemetry event(s) the label is about (non-empty).
        rationale: a short human justification for the label.
        labeler: optional id of the primary labeler.
        second_label: optional boolean label from a second labeler (for IRR).
        source: optional provenance (subject/sha/host) when drawn from a repo.
    """

    id: str
    bug_class: str
    label: bool
    events: list[dict[str, Any]]
    rationale: str
    labeler: str | None = None
    second_label: bool | None = None
    source: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "bug_class": self.bug_class,
            "label": self.label,
            "events": self.events,
            "rationale": self.rationale,
        }
        if self.labeler is not None:
            out["labeler"] = self.labeler
        if self.second_label is not None:
            out["second_label"] = self.second_label
        if self.source is not None:
            out["source"] = self.source
        return out


def _coerce_item(raw: Any, *, line_no: int, seen: set[str]) -> GoldItem:
    if not isinstance(raw, dict):
        raise GroundTruthError(f"line {line_no}: each gold sample must be a JSON object")

    item_id = raw.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise GroundTruthError(f"line {line_no}: 'id' must be a non-empty string")
    if item_id in seen:
        raise GroundTruthError(f"line {line_no}: duplicate id {item_id!r}")

    bug_class = raw.get("bug_class")
    if bug_class not in _BUG_CLASS_SET:
        raise GroundTruthError(
            f"line {line_no} ({item_id}): 'bug_class' must be one of {sorted(_BUG_CLASS_SET)}"
        )

    label = raw.get("label")
    if not isinstance(label, bool):
        raise GroundTruthError(f"line {line_no} ({item_id}): 'label' must be a boolean")

    events = raw.get("events")
    if not isinstance(events, list) or not events or not all(isinstance(e, dict) for e in events):
        raise GroundTruthError(
            f"line {line_no} ({item_id}): 'events' must be a non-empty list of objects"
        )

    rationale = raw.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise GroundTruthError(f"line {line_no} ({item_id}): 'rationale' must be a non-empty string")

    labeler = raw.get("labeler")
    if labeler is not None and not isinstance(labeler, str):
        raise GroundTruthError(f"line {line_no} ({item_id}): 'labeler' must be a string when present")

    second_label = raw.get("second_label")
    if second_label is not None and not isinstance(second_label, bool):
        raise GroundTruthError(
            f"line {line_no} ({item_id}): 'second_label' must be a boolean when present"
        )

    source = raw.get("source")
    if source is not None and not isinstance(source, dict):
        raise GroundTruthError(f"line {line_no} ({item_id}): 'source' must be an object when present")

    seen.add(item_id)
    return GoldItem(
        id=item_id,
        bug_class=bug_class,
        label=label,
        events=events,
        rationale=rationale.strip(),
        labeler=labeler,
        second_label=second_label,
        source=source,
    )


def parse_gold_lines(text: str) -> list[GoldItem]:
    """Parse JSONL gold text into validated, id-sorted :class:`GoldItem` records."""

    items: list[GoldItem] = []
    seen: set[str] = set()
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GroundTruthError(f"line {line_no}: invalid JSON ({exc.msg})") from exc
        items.append(_coerce_item(obj, line_no=line_no, seen=seen))
    if not items:
        raise GroundTruthError("gold set is empty")
    items.sort(key=lambda it: it.id)
    return items


def load_gold_set(*paths: str | Path) -> list[GoldItem]:
    """Load and merge one or more gold JSONL files (ids must be globally unique)."""

    if not paths:
        raise GroundTruthError("no gold paths provided")
    chunks: list[str] = []
    for path in paths:
        p = Path(path)
        if not p.exists():
            raise GroundTruthError(f"gold file not found: {p}")
        chunks.append(p.read_text(encoding="utf-8"))
    return parse_gold_lines("\n".join(chunks))
