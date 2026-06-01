"""Offline tests for the content-addressed corpus cache and pure analysis helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from telemetry_contracts.mining.cache import (
    ResultCache,
    analysis_key,
    atomic_write_json,
    engine_fingerprint,
    options_fingerprint,
)


def test_engine_fingerprint_is_deterministic():
    assert engine_fingerprint() == engine_fingerprint()
    assert len(engine_fingerprint()) == 64


def test_engine_fingerprint_changes_when_a_module_changes(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "a.py").write_text("x = 1\n", encoding="utf-8")
    before = engine_fingerprint(pkg)
    # Editing a module changes the fingerprint (fail-closed invalidation).
    (pkg / "a.py").write_text("x = 2\n", encoding="utf-8")
    after_edit = engine_fingerprint(pkg)
    assert after_edit != before
    # Adding a new module also changes it (never a stale hit on new analysis code).
    (pkg / "b.py").write_text("y = 0\n", encoding="utf-8")
    after_add = engine_fingerprint(pkg)
    assert after_add != after_edit


def test_options_fingerprint_is_order_independent():
    a = options_fingerprint({"max_files": 1, "service": None})
    b = options_fingerprint({"service": None, "max_files": 1})
    assert a == b
    assert a != options_fingerprint({"max_files": 2, "service": None})


def test_analysis_key_depends_on_all_components():
    base = analysis_key("a" * 40, "eng", "opt")
    assert base != analysis_key("b" * 40, "eng", "opt")
    assert base != analysis_key("a" * 40, "eng2", "opt")
    assert base != analysis_key("a" * 40, "eng", "opt2")


def test_atomic_write_json_roundtrip(tmp_path):
    target = tmp_path / "nested" / "out.json"
    atomic_write_json(target, {"b": 2, "a": 1})
    text = target.read_text(encoding="utf-8")
    # Canonical: sorted keys, trailing newline, no leftover temp files.
    assert text.endswith("\n")
    assert json.loads(text) == {"a": 1, "b": 2}
    assert list(text.splitlines()[1:3]) == ['  "a": 1,', '  "b": 2']
    assert list(tmp_path.glob("nested/.*tmp*")) == []


def test_result_cache_get_put_and_key_invalidation(tmp_path):
    facts = {"has_telemetry": True, "event_count": 7}
    cache = ResultCache(tmp_path, engine_fp="ENG", options={"max_files": 1})
    assert cache.get("d" * 40) is None
    cache.put("d" * 40, facts)
    assert cache.get("d" * 40) == facts

    # A different engine fingerprint must miss (stale engine never served).
    other_engine = ResultCache(tmp_path, engine_fp="ENG2", options={"max_files": 1})
    assert other_engine.get("d" * 40) is None

    # A different options key must miss.
    other_opts = ResultCache(tmp_path, engine_fp="ENG", options={"max_files": 2})
    assert other_opts.get("d" * 40) is None


def test_result_cache_survives_corrupt_entry(tmp_path):
    cache = ResultCache(tmp_path, engine_fp="ENG", options={})
    cache.put("e" * 40, {"ok": True})
    # Corrupt the stored entry; get must degrade to a miss, not raise.
    entry = next((tmp_path / "results").glob("*.json"))
    entry.write_text("{not json", encoding="utf-8")
    assert cache.get("e" * 40) is None
