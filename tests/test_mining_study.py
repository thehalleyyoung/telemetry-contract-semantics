"""Offline tests for the corpus mining study (no network).

These exercise manifest validation, per-subject reduction, deterministic
aggregation (headline statistic, prevalence, score distribution), and report
rendering using real ``scan_directory`` + ``diagnose`` over local fixture
directories. Network proof on real repositories lives in
``tests/test_real_repos.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from telemetry_contracts.bug_classes import (
    BUG_CLASS_IDS,
    CODE_TO_BUG_CLASS,
    HEADLINE_GAP,
    soundness_rows,
)
from telemetry_contracts.mining import (
    aggregate,
    parse_corpus_manifest,
    render_study_markdown,
    subject_record,
)
from telemetry_contracts.mining.corpus import CorpusManifestError, CorpusSubject
from telemetry_contracts.mining.study import _nearest_rank, _permille
from telemetry_contracts.pipeline import diagnose
from telemetry_contracts.repo_scan import scan_directory


# --------------------------------------------------------------------------
# Bug-class single source of truth
# --------------------------------------------------------------------------


def test_bug_class_codes_are_in_taxonomy():
    from telemetry_contracts.findings import TAXONOMY

    for gap, entry in zip(BUG_CLASS_IDS, (soundness_rows())):
        for code in entry["finding_codes"]:
            assert code in TAXONOMY, f"{code} for {gap} must exist in TAXONOMY"


def test_soundness_rows_have_guarantee_and_incompleteness():
    rows = soundness_rows()
    assert {r["id"] for r in rows} == set(BUG_CLASS_IDS)
    for r in rows:
        assert r["guarantee"] and r["incompleteness"] and r["definition"]
        assert r["blocks_question"]


def test_headline_gap_is_a_known_bug_class():
    assert HEADLINE_GAP in BUG_CLASS_IDS
    assert "telemetry.correlation_missing" in CODE_TO_BUG_CLASS


# --------------------------------------------------------------------------
# Manifest validation
# --------------------------------------------------------------------------


def _valid_manifest():
    return {
        "schema": "telemetry-contracts/corpus@1",
        "selection_protocol": {"description": "demo", "criteria": ["lang=py"]},
        "subjects": [
            {"target": "owner/repo", "sha": "a" * 40, "host": "github", "license": "MIT", "tier": 1},
            {"target": "gl:group/project", "sha": "b" * 40, "license": "Apache-2.0", "tier": 2},
        ],
    }


def test_parse_valid_manifest_sorts_and_infers_host():
    protocol, subjects = parse_corpus_manifest(_valid_manifest())
    assert protocol["description"] == "demo"
    assert [s.target for s in subjects] == ["owner/repo", "gl:group/project"]
    # host inferred for the second subject
    assert subjects[1].host == "gitlab"
    assert subjects[0].clone_url == "https://github.com/owner/repo.git"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda m: m.update(schema="x"), "schema"),
        (lambda m: m.update(subjects=[]), "non-empty"),
        (lambda m: m["subjects"][0].update(sha="z" * 40), "hex commit SHA"),
        (lambda m: m["subjects"][0].update(sha="abc"), "hex commit SHA"),
        (lambda m: m["subjects"][0].update(target=""), "non-empty string"),
        (lambda m: m["subjects"][0].update(target="not a repo target!!"), "invalid"),
        (lambda m: m["subjects"][0].update(tier=0), "positive integer"),
    ],
)
def test_parse_invalid_manifest(mutate, message):
    m = _valid_manifest()
    mutate(m)
    with pytest.raises(CorpusManifestError) as exc:
        parse_corpus_manifest(m)
    assert message in str(exc.value)


def test_parse_rejects_duplicate_subjects():
    m = _valid_manifest()
    m["subjects"][1] = dict(m["subjects"][0])
    with pytest.raises(CorpusManifestError) as exc:
        parse_corpus_manifest(m)
    assert "duplicate" in str(exc.value)


# --------------------------------------------------------------------------
# Arithmetic helpers (determinism)
# --------------------------------------------------------------------------


def test_permille_rounding():
    assert _permille(0, 0) == 0
    assert _permille(1, 2) == 500
    assert _permille(2, 3) == 667  # 0.6667 -> 667
    assert _permille(1, 3) == 333


def test_nearest_rank_percentiles():
    values = [10, 20, 30, 40]
    assert _nearest_rank(values, 25) == 10
    assert _nearest_rank(values, 50) == 20
    assert _nearest_rank(values, 75) == 30
    assert _nearest_rank(values, 100) == 40


# --------------------------------------------------------------------------
# End-to-end reduction over real local fixture directories
# --------------------------------------------------------------------------


def _write_jsonl(path: Path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def _reduce_dir(subject: CorpusSubject, root: Path):
    scan_report = scan_directory(root)
    # union diagnosis over the same telemetry files
    from telemetry_contracts.mining.study import _repo_diagnosis

    diagnosis = _repo_diagnosis(root, max_total_events=10000, max_events_per_file=10000, service=None)
    return subject_record(subject, scan_report, diagnosis)


def test_subject_record_flags_headline_gap(tmp_path):
    # A repo with failure events that carry no correlation id.
    repo = tmp_path / "under_instrumented"
    _write_jsonl(
        repo / "logs" / "app.jsonl",
        [{"kind": "event", "name": "checkout", "severity": "error"} for _ in range(5)],
    )
    subject = CorpusSubject("acme/under", "a" * 40, "github", "MIT", "", 1)
    record = _reduce_dir(subject, repo)

    assert record["has_telemetry"] is True
    assert record["event_count"] == 5
    assert record["headline_blocked"] is True
    assert record["bug_class_present"]["missing-correlation"] is True
    assert record["diagnosability_score"] is not None


def test_subject_record_clean_repo_not_blocked(tmp_path):
    repo = tmp_path / "well_instrumented"
    _write_jsonl(
        repo / "telemetry" / "spans.jsonl",
        [{"kind": "span", "name": "op", "severity": "info", "trace_id": f"t{i}", "duration_ms": 5}
         for i in range(5)],
    )
    subject = CorpusSubject("acme/clean", "c" * 40, "github", "MIT", "", 1)
    record = _reduce_dir(subject, repo)

    assert record["headline_blocked"] is False
    assert record["bug_class_present"]["missing-correlation"] is False


def test_no_telemetry_repo_degrades_gracefully(tmp_path):
    repo = tmp_path / "empty"
    repo.mkdir()
    (repo / "README.md").write_text("# nothing here\n", encoding="utf-8")
    subject = CorpusSubject("acme/empty", "e" * 40, "github", "MIT", "", 1)
    record = _reduce_dir(subject, repo)

    assert record["has_telemetry"] is False
    assert record["diagnosability_score"] is None
    assert record["headline_blocked"] is False


def test_aggregate_headline_and_determinism(tmp_path):
    blocked_repo = tmp_path / "b"
    _write_jsonl(blocked_repo / "a.jsonl",
                 [{"kind": "event", "name": "x", "severity": "error"} for _ in range(3)])
    clean_repo = tmp_path / "c"
    _write_jsonl(clean_repo / "a.jsonl",
                 [{"kind": "span", "name": "op", "severity": "info", "trace_id": "t", "duration_ms": 2}])
    empty_repo = tmp_path / "e"
    empty_repo.mkdir()
    (empty_repo / "README").write_text("x", encoding="utf-8")

    records = [
        _reduce_dir(CorpusSubject("o/blocked", "a" * 40, "github", "MIT", "", 1), blocked_repo),
        _reduce_dir(CorpusSubject("o/clean", "b" * 40, "gitlab", "MIT", "", 1), clean_repo),
        _reduce_dir(CorpusSubject("o/empty", "c" * 40, "bitbucket", "MIT", "", 1), empty_repo),
    ]
    ds = aggregate(records)

    assert ds["subjects_total"] == 3
    assert ds["subjects_with_telemetry"] == 2
    # Headline denominator is now telemetry-bearing repos with >=1 failure event.
    # Only the "blocked" repo has failure events, so denominator == 1.
    assert ds["headline"]["denominator"] == 1
    assert ds["headline"]["cannot_answer"] == 1
    assert ds["headline"]["cannot_answer_permille"] == 1000
    assert ds["headline"]["subjects_with_telemetry"] == 2
    assert ds["headline"]["share_of_telemetry_permille"] == 500
    assert ds["hosts"] == ["bitbucket", "github", "gitlab"]
    prev = ds["bug_class_prevalence"]["missing-correlation"]
    assert prev["subjects_present"] == 1
    assert prev["subjects_present_permille"] == 500

    # Determinism: aggregating the same records (any order) is byte-identical.
    again = aggregate(list(reversed(records)))
    assert json.dumps(ds, sort_keys=True) == json.dumps(again, sort_keys=True)


def test_mean_milli_half_up():
    from telemetry_contracts.mining.study import _mean_milli

    # mean of [1,2] = 1.5 -> 1500 milli (half-up)
    assert _mean_milli([1, 2]) == 1500
    # mean of [1,1,2] = 1.333... -> 1333
    assert _mean_milli([1, 1, 2]) == 1333


def test_scan_and_diagnosis_use_same_file_cap(tmp_path, monkeypatch):
    # Two telemetry files; cap discovery at 1 file. Both the scan and the
    # union diagnosis must see the SAME single file, so presence and score stay
    # internally consistent regardless of the cap.
    repo = tmp_path / "many"
    _write_jsonl(repo / "a.jsonl",
                 [{"kind": "event", "name": "x", "severity": "error"}])
    _write_jsonl(repo / "b.jsonl",
                 [{"kind": "span", "name": "op", "severity": "info", "trace_id": "t", "duration_ms": 1}])

    from telemetry_contracts.mining.study import _repo_diagnosis
    from telemetry_contracts.repo_scan import scan_directory

    scan_report = scan_directory(repo, max_files=1)
    diagnosis = _repo_diagnosis(repo, max_total_events=100, max_events_per_file=100,
                                service=None, max_files=1)
    subject = CorpusSubject("o/many", "a" * 40, "github", "MIT", "", 1)
    record = subject_record(subject, scan_report, diagnosis)
    # Exactly one telemetry file was considered by both paths.
    assert record["telemetry_files"] == 1
    assert diagnosis is not None



    repo = tmp_path / "b"
    _write_jsonl(repo / "a.jsonl",
                 [{"kind": "event", "name": "x", "severity": "error"} for _ in range(2)])
    ds = aggregate([_reduce_dir(CorpusSubject("o/b", "a" * 40, "github", "MIT", "", 1), repo)])
    md1 = render_study_markdown(ds)
    md2 = render_study_markdown(ds)
    assert md1 == md2
    assert "Headline finding" in md1
    assert "Why did this request fail" in md1
    assert "Bug-class prevalence" in md1
