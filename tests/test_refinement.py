from __future__ import annotations

import json

from telemetry_contracts.cli import main
from telemetry_contracts.refinement import check_contract_refinement, format_refinement_markdown


def _base_contract() -> dict:
    return {
        "service": "checkout",
        "version": 1,
        "metadata": {
            "strict_validation": {"enabled": True, "allowed_extra_fields": ["trace_id"]},
            "transformation_preservation": {
                "approved_transformations": ["redacted"],
                "preserve_scenarios": ["triage"],
            },
        },
        "privacy_classifications": {
            "identifier": {"allowed_transformations": ["hashed", "redacted"]},
            "pii": {"allowed_transformations": ["redacted"]},
        },
        "spans": [
            {
                "name": "checkout.charge",
                "required": True,
                "attributes": {
                    "tenant_id": {"type": "string", "required": True, "classification": "identifier", "transformation": "hashed"},
                    "amount": {"type": "number", "required": True, "min": 0},
                },
            }
        ],
        "metrics": [
            {
                "name": "checkout.errors",
                "required": True,
                "value": {"type": "number", "min": 0, "max": 100},
                "tags": {"reason": {"type": "string", "required": True, "allowed_values": ["declined", "timeout"]}},
            }
        ],
        "logs": [
            {
                "name": "checkout.failure",
                "required": True,
                "severity": "ERROR",
                "fields": {"message": {"type": "string", "required": True, "forbidden_patterns": ["password="]}},
            }
        ],
        "scenarios": [{"id": "triage", "question": "Why did checkout fail?", "requires": [{"kind": "span", "name": "checkout.charge"}]}],
        "temporal_properties": [
            {
                "id": "response",
                "type": "bounded_response",
                "description": "respond quickly",
                "trigger": {"kind": "span", "name": "checkout.charge"},
                "response": {"kind": "log", "name": "checkout.failure"},
                "within_ms": 1000,
            }
        ],
        "alternative_obligations": [
            {
                "id": "rollback-or-alert",
                "required": True,
                "any_of": [{"id": "alert", "signal": "log", "name": "checkout.failure", "fields": ["message"]}],
            }
        ],
        "assume_guarantee": {
            "collector_assumptions": [{"id": "collector_keeps_required", "no_undocumented_transformations": True}],
            "service_guarantees": [{"id": "emits_charge", "signal": "span", "name": "checkout.charge"}],
        },
    }


def test_refinement_accepts_strengthening_candidate() -> None:
    candidate = _base_contract()
    candidate["spans"][0]["attributes"]["amount"]["max"] = 10_000
    candidate["metrics"][0]["value"]["max"] = 50
    candidate["metrics"][0]["tags"]["reason"]["allowed_values"] = ["timeout"]
    candidate["spans"][0]["attributes"]["request_id"] = {"type": "string", "required": True}

    report = check_contract_refinement(_base_contract(), candidate)

    assert report["summary"]["refines"] is True
    assert report["findings"] == []
    assert "Contract-refinement report" in format_refinement_markdown(report)


def test_refinement_reports_weakened_requirements_and_policies() -> None:
    candidate = _base_contract()
    candidate["spans"][0]["attributes"].pop("tenant_id")
    candidate["metrics"][0]["value"].pop("max")
    candidate["metrics"][0]["tags"]["reason"]["allowed_values"] = ["declined", "timeout", "unknown"]
    candidate["logs"][0]["severity"] = "INFO"
    candidate["metadata"]["strict_validation"] = {"enabled": False, "allowed_extra_fields": ["trace_id", "email"]}
    candidate["assume_guarantee"]["collector_assumptions"].append({"id": "collector_retains_forever", "no_undocumented_transformations": True})

    report = check_contract_refinement(_base_contract(), candidate)
    codes = {finding["code"] for finding in report["findings"]}

    assert report["summary"]["refines"] is False
    assert "refinement.required_field_removed" in codes
    assert "refinement.field_predicate_weakened" in codes
    assert "refinement.strict_policy_weakened" in codes
    assert "refinement.assumption_strengthened" in codes


def test_refinement_cli_writes_json_report(tmp_path) -> None:
    base = tmp_path / "base.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "report.json"
    contract = _base_contract()
    base.write_text(json.dumps(contract), encoding="utf-8")
    candidate.write_text(json.dumps(contract), encoding="utf-8")

    rc = main(
        [
            "refinement",
            "--base-contract",
            str(base),
            "--candidate-contract",
            str(candidate),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )

    assert rc == 0
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["refines"] is True
