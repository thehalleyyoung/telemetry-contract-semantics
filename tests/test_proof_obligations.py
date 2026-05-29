from pathlib import Path

from telemetry_contracts.loader import load_contract, load_jsonl
from telemetry_contracts.proof_obligations import generate_proof_obligations_report

ROOT = Path(__file__).resolve().parents[1]


def test_proof_obligations_discharge_checkout_with_benchmark():
    report = generate_proof_obligations_report(
        load_contract(ROOT / "examples/contracts/checkout.contract.json"),
        load_jsonl(ROOT / "examples/telemetry/passing.jsonl"),
        benchmark_config=str(ROOT / "benchmarks/builtin.json"),
    )

    assert report["summary"]["features_cataloged"] == 24
    assert report["summary"]["violated"] == 0
    assert report["summary"]["family_counts"]["well-formedness"] > 0
    assert report["summary"]["family_counts"]["satisfaction"] > 0
    assert report["summary"]["family_counts"]["monitor-soundness"] > 0
    assert any(item["formal_clause"] == "BENCH.label-validity" and item["status"] == "discharged" for item in report["obligations"])


def test_proof_obligations_surface_historical_strict_and_preservation_evidence():
    case = ROOT / "case_studies/gitlab_2017_database_outage"
    report = generate_proof_obligations_report(
        load_contract(case / "contract.json"),
        load_jsonl(case / "reconstructed_events_strict_drift.jsonl"),
        strict=True,
        source_events=load_jsonl(case / "reconstructed_events.jsonl"),
        transformed_events=load_jsonl(case / "reconstructed_events_sampled_missing_alert.jsonl"),
    )

    violated_clauses = {item["formal_clause"] for item in report["obligations"] if item["status"] == "violated"}
    assert "STRICT.field-closed-world" in violated_clauses
    assert "STRICT.signal-closed-world" in violated_clauses
    assert "STRICT.transformation-documented" in violated_clauses
    assert "PRES.adequacy-signal" in violated_clauses
