from __future__ import annotations

import json

from telemetry_contracts.cli import main
from telemetry_contracts.composition import analyze_contract_composition, format_composition_markdown
from telemetry_contracts.loader import load_contract
from telemetry_contracts.validator import validate_events


def _parent_contract() -> dict:
    return {
        "version": "1.0",
        "service": "organization",
        "metadata": {"refinement_scope": "organization"},
        "logs": [
            {
                "name": "checkout.failure",
                "required": True,
                "severity": "ERROR",
                "fields": {
                    "tenant_id": {"type": "string", "required": True},
                    "reason": {"type": "string", "required": True, "allowed_values": ["timeout", "declined"]},
                },
            }
        ],
        "scenarios": [
            {
                "id": "failure-triage",
                "question": "Can support identify tenant and failure reason?",
                "requires": [{"signal": "log", "name": "checkout.failure", "fields": ["tenant_id", "reason"]}],
            }
        ],
    }


def test_load_contract_resolves_inherited_signal_obligations(tmp_path) -> None:
    parent = tmp_path / "org.json"
    child = tmp_path / "service.json"
    parent.write_text(json.dumps(_parent_contract()), encoding="utf-8")
    child.write_text(
        json.dumps(
            {
                "extends": "org.json",
                "version": "1.0",
                "service": "checkout",
                "logs": [
                    {
                        "name": "checkout.failure",
                        "fields": {"request_id": {"type": "string", "required": True}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    contract = load_contract(child)

    fields = contract["logs"][0]["fields"]
    assert set(fields) == {"tenant_id", "reason", "request_id"}
    assert validate_events(
        contract,
        [
            {
                "kind": "log",
                "service": "checkout",
                "name": "checkout.failure",
                "severity": "ERROR",
                "fields": {"tenant_id": "tenant-a", "reason": "timeout", "request_id": "req-1"},
            }
        ],
    ) == []


def test_composition_report_uses_refinement_to_reject_weakening(tmp_path) -> None:
    parent = tmp_path / "org.json"
    child = tmp_path / "service.json"
    parent.write_text(json.dumps(_parent_contract()), encoding="utf-8")
    child.write_text(
        json.dumps(
            {
                "extends": "org.json",
                "version": "1.0",
                "service": "checkout",
                "logs": [
                    {
                        "name": "checkout.failure",
                        "severity": "INFO",
                        "fields": {"reason": {"type": "string", "required": False, "allowed_values": ["timeout", "declined", "unknown"]}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = analyze_contract_composition(child)
    codes = {finding["code"] for finding in report["findings"]}

    assert report["summary"]["valid"] is False
    assert "refinement.required_field_removed" in codes
    assert "refinement.field_predicate_weakened" in codes
    assert "Contract-composition report" in format_composition_markdown(report)


def test_compose_contract_cli_writes_report_and_resolved_contract(tmp_path) -> None:
    parent = tmp_path / "org.json"
    child = tmp_path / "service.json"
    output = tmp_path / "composition.json"
    resolved = tmp_path / "resolved.json"
    parent.write_text(json.dumps(_parent_contract()), encoding="utf-8")
    child.write_text(json.dumps({"extends": "org.json", "version": "1.0", "service": "checkout"}), encoding="utf-8")

    rc = main([
        "compose-contract",
        "--contract",
        str(child),
        "--format",
        "json",
        "--output",
        str(output),
        "--resolved-output",
        str(resolved),
    ])

    assert rc == 0
    assert json.loads(output.read_text(encoding="utf-8"))["summary"]["valid"] is True
    assert json.loads(resolved.read_text(encoding="utf-8"))["logs"][0]["name"] == "checkout.failure"
