from pathlib import Path

from telemetry_contracts.core_semantics import evaluate_contract_semantics, format_core_semantics_markdown
from telemetry_contracts.loader import load_contract, load_jsonl


ROOT = Path(__file__).resolve().parents[1]


def _golden(contract_path: str, events_path: str, *, strict: bool | None = None):
    return evaluate_contract_semantics(
        load_contract(ROOT / contract_path),
        load_jsonl(ROOT / events_path),
        strict=strict,
    )


def test_small_step_semantics_aligns_on_passing_checkout_fixture():
    report = _golden("examples/contracts/checkout.contract.json", "examples/telemetry/passing.jsonl")

    assert report["summary"]["pass"] is True
    assert report["summary"]["aligned_with_checker"] is True
    assert report["denotation"]["mismatches"] == {"missing_from_small_step": [], "extra_in_small_step": []}
    assert any(step["rule"] == "SIGNAL" and step["evidence"]["matching_event_lines"] for step in report["small_steps"])
    assert "Small-step derivation" in format_core_semantics_markdown(report)


def test_small_step_semantics_aligns_on_failing_checkout_fixture():
    report = _golden("examples/contracts/checkout.contract.json", "examples/telemetry/failing.jsonl")

    assert report["summary"]["pass"] is False
    assert report["summary"]["aligned_with_checker"] is True
    assert report["summary"]["findings_by_code"]["telemetry.missing_signal"] == 1
    assert any(step["status"] == "violated" for step in report["small_steps"])


def test_small_step_semantics_aligns_with_strict_historical_fixture():
    report = _golden(
        "case_studies/gitlab_2017_database_outage/contract.json",
        "case_studies/gitlab_2017_database_outage/reconstructed_events_strict_drift.jsonl",
        strict=True,
    )

    assert report["summary"]["aligned_with_checker"] is True
    assert report["summary"]["findings_by_code"]["telemetry.strict_unexpected_field"] == 2
    assert any(step["rule"] == "STRICT" and step["finding_count"] == 5 for step in report["small_steps"])
