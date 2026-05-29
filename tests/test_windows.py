from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.windows import format_event_window_markdown, generate_event_window_report

ROOT = Path(__file__).resolve().parents[1]


def test_event_window_report_groups_findings_by_tenant_and_incident_slice():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    events = load_jsonl(ROOT / "examples/telemetry/failing.jsonl")

    report = generate_event_window_report(contract, events, dimensions=["tenant"], incident_slice_ms=1000)

    assert report["model"]["name"] == "event-window-grouping-v1"
    assert report["summary"]["pass"] is False
    assert report["summary"]["windows_with_findings"] >= 2
    tenant_window = next(window for window in report["windows"] if window["id"] == "tenant:tenant_id=tenant-acme")
    assert tenant_window["summary"]["event_count"] == 3
    assert "telemetry.allowed_values" in tenant_window["summary"]["finding_codes"]
    assert "Event-window report" in format_event_window_markdown(report)


def test_event_window_report_localizes_historical_gitlab_findings():
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    contract = load_contract(case / "contract.json")
    events = load_jsonl(case / "reconstructed_events_sampled_missing_alert.jsonl")

    report = generate_event_window_report(contract, events, dimensions=["incident"], incident_slice_ms=2000)

    incident = next(window for window in report["windows"] if window["id"] == "incident:incident_id=gitlab-2017-db-outage")
    assert incident["summary"]["finding_codes"]["telemetry.numeric_max"] == 1
    assert report["summary"]["findings_by_code"]["telemetry.temporal_response"] == 1
    assert any(window["id"] == "global:contract=all" for window in report["windows"])
