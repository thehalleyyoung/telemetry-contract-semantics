from pathlib import Path

from telemetry_contracts.equivalence import compare_observational_equivalence, format_equivalence_markdown
from telemetry_contracts.loader import load_contract, load_jsonl

ROOT = Path(__file__).resolve().parents[1]
GITLAB = ROOT / "case_studies/gitlab_2017_database_outage"


def test_observational_equivalence_ignores_byte_changes_that_preserve_answerability():
    contract = load_contract(str(GITLAB / "contract.json"))
    left = load_jsonl(str(GITLAB / "reconstructed_events.jsonl"))
    right = list(reversed(left))

    report = compare_observational_equivalence(contract, left, right, ["restore-readiness"])

    assert report["equivalent"] is True
    assert report["summary"]["questions_compared"] == 1
    assert report["comparisons"][0]["deltas"] == []
    assert "Observational-equivalence" in format_equivalence_markdown(report)


def test_observational_equivalence_reports_sampled_missing_evidence_on_historical_fixture():
    contract = load_contract(str(GITLAB / "contract.json"))
    left = load_jsonl(str(GITLAB / "reconstructed_events.jsonl"))
    right = load_jsonl(str(GITLAB / "reconstructed_events_sampled_missing_alert.jsonl"))

    report = compare_observational_equivalence(contract, left, right, ["restore-readiness"])

    assert report["equivalent"] is False
    assert report["summary"]["different_questions"] == 1
    deltas = report["comparisons"][0]["deltas"]
    assert {"requirement": "$question", "field": "answerable", "left": "false", "right": "false"} not in deltas
    assert any(delta["requirement"] == "log:backup.pg_dump.failed" and delta["field"] == "$signal" for delta in deltas)
    assert any(delta["requirement"] == "log:backup.pg_dump.failed" and delta["field"] == "alert_route" for delta in deltas)
