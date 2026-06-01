"""Content-addressed cache for corpus mining (pure stdlib).

Re-running the corpus over hundreds of repositories should be *incremental*: a
subject whose pinned commit and whose analysing engine are both unchanged must
not be re-cloned or re-analysed. We make that property explicit and verifiable
with a content-addressed cache keyed by an ``analysis_key``::

    analysis_key = sha256(
        subject_sha + engine_fingerprint + options_fingerprint + CACHE_SCHEMA
    )

* ``subject_sha`` — the exact commit studied (the pinned input).
* ``engine_fingerprint`` — a sha256 over *all* package source, so any change to
  the analysing code invalidates the cache. This deliberately *fails closed*:
  cosmetic edits (e.g. to the CLI) also invalidate, which is acceptable — we
  never want a stale hit, and recomputing is cheap relative to a wrong number.
* ``options_fingerprint`` — the scan/diagnosis bounds (``max_files`` etc.), since
  those change the result.
* ``CACHE_SCHEMA`` — bumped if the stored record shape changes.

Only *analysis-derived facts* are cached (see ``mining.study.record_facts``);
mutable manifest metadata (license, tier, rationale, host) is merged back at
aggregation time, so a cache entry is reusable across manifests that pin the same
commit. All writes are atomic (temp file + ``fsync`` + ``os.replace``) so a crash
mid-write can never leave a half-written, falsely-trusted entry.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

CACHE_SCHEMA = "telemetry-contracts/corpus-cache@1"

# The package whose source defines the analysis. Hashing *all* of it (rather than
# an allowlist) guarantees we never serve a stale result from a module we forgot
# to list; the cost is honest over-invalidation on unrelated edits.
_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def engine_fingerprint(package_root: Path | None = None) -> str:
    """A sha256 over every ``.py`` file in the package, path- and byte-sensitive.

    Deterministic: files are visited in sorted POSIX-relative order and both the
    relative path and the raw bytes feed the hash, so adding, removing, renaming,
    or editing any module changes the fingerprint.
    """

    root = (package_root or _PACKAGE_ROOT).resolve()
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py"), key=lambda p: p.relative_to(root).as_posix()):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def options_fingerprint(options: dict[str, Any]) -> str:
    """A short, stable fingerprint of the scan/diagnosis options."""

    blob = json.dumps(options, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def analysis_key(subject_sha: str, engine_fp: str, options_fp: str) -> str:
    """The content-addressed cache key for one analysed subject."""

    digest = hashlib.sha256()
    for part in (subject_sha, engine_fp, options_fp, CACHE_SCHEMA):
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: Any) -> None:
    """Write ``payload`` as canonical JSON atomically (crash-safe)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    data = json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    # Best-effort directory fsync so the rename is durable where supported.
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


class ResultCache:
    """A directory-backed, content-addressed cache of per-subject analysis facts."""

    def __init__(self, cache_dir: str | Path, *, engine_fp: str | None = None,
                 options: dict[str, Any] | None = None) -> None:
        self.root = Path(cache_dir)
        self.results_dir = self.root / "results"
        self.engine_fp = engine_fp if engine_fp is not None else engine_fingerprint()
        self.options_fp = options_fingerprint(options or {})

    def _path(self, subject_sha: str) -> Path:
        key = analysis_key(subject_sha, self.engine_fp, self.options_fp)
        return self.results_dir / f"{key}.json"

    def get(self, subject_sha: str) -> dict[str, Any] | None:
        """Return cached facts for ``subject_sha`` under the current key, or None."""

        path = self._path(subject_sha)
        if not path.is_file():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        # Defensive: a stored entry must echo its key components.
        if entry.get("engine_fingerprint") != self.engine_fp:
            return None
        if entry.get("options_fingerprint") != self.options_fp:
            return None
        facts = entry.get("facts")
        return facts if isinstance(facts, dict) else None

    def put(self, subject_sha: str, facts: dict[str, Any]) -> None:
        """Store ``facts`` for ``subject_sha`` under the current key, atomically."""

        entry = {
            "schema": CACHE_SCHEMA,
            "subject_sha": subject_sha,
            "engine_fingerprint": self.engine_fp,
            "options_fingerprint": self.options_fp,
            "facts": facts,
        }
        atomic_write_json(self._path(subject_sha), entry)
