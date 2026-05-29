from pathlib import Path

from telemetry_contracts.assume_guarantee import evaluate_assume_guarantee
from telemetry_contracts.cli import main
from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.validator import validate_contract_shape

ROOT = Path(__file__).resolve().parents[1]


def test_assume_guarantee_partitions_layer_obligations():
    contract = {
        "version": "1.0",
        "service": "svc",
        "assume_guarantee": {
            "service_guarantees": [
                {"id": "emit-request", "signal": "span", "name": "request", "fields": ["trace_id"]},
            ],
            "collector_assumptions": [
                {"id": "document-transforms", "no_undocumented_transformations": True, "approved_transformations": ["redaction"]},
            ],
            "oncall_obligations": [
                {"id": "alert-delivered", "signal": "log", "name": "alert", "field": "delivered", "equals": True},
            ],
        },
    }
    events = [
        {"kind": "span", "service": "svc", "name": "request", "attributes": {"trace_id": "t1"}, "transformations": ["tail_sampling"]},
        {"kind": "log", "service": "svc", "name": "alert", "fields": {"delivered": False}},
    ]

    report = evaluate_assume_guarantee(contract, events)

    assert report["summary"]["satisfied"] == 1
    assert report["summary"]["violated"] == 2
    assert report["summary"]["findings_by_code"]["ag.undocumented_transformation"] == 1
    assert report["summary"]["findings_by_code"]["ag.predicate"] == 1
    assert report["summary"]["by_layer"]["service"]["satisfied"] == 1
    assert report["summary"]["by_layer"]["collector"]["violated"] == 1
    assert report["summary"]["by_layer"]["oncall"]["violated"] == 1


def test_assume_guarantee_lint_rejects_malformed_obligation():
    findings = validate_contract_shape(
        {
            "version": "1.0",
            "service": "svc",
            "assume_guarantee": {"service_guarantees": [{"id": "", "fields": "trace_id"}]},
        }
    )

    assert "contract.assume_guarantee" in {finding.code for finding in findings}


def test_cli_assume_guarantee_reports_historical_layer_failures(capsys):
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    code = main(
        [
            "report",
            "assume-guarantee",
            "--contract",
            str(case / "contract.json"),
            "--events",
            str(case / "reconstructed_events_sampled_missing_alert.jsonl"),
            "--format",
            "json",
            "--fail-on",
            "never",
        ]
    )
    output = capsys.readouterr().out

    assert code == 0
    assert '"service": "gitlab.com-database"' in output
    assert "ag.missing_signal" in output
    assert "backup-alert-delivered-to-responders" in output


def test_historical_reconstructed_assume_guarantee_is_bounded_evidence():
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    report = evaluate_assume_guarantee(load_contract(case / "contract.json"), load_jsonl(case / "reconstructed_events.jsonl"))

    assert report["summary"]["obligations"] >= 4
    assert report["summary"]["by_layer"]["service"]["violated"] >= 1
    assert report["summary"]["by_layer"]["oncall"]["violated"] >= 1
