from __future__ import annotations

import copy
import json
from pathlib import Path

from telemetry_contracts.cli import main
from telemetry_contracts.contract_diff import format_contract_diff_markdown, generate_contract_diff_report

ROOT = Path(__file__).resolve().parents[1]


def _contract() -> dict:
    return {
        "version": 1,
        "service": "checkout",
        "privacy_classifications": {
            "identifier": {"allowed_transformations": ["hashed", "redacted"]},
        },
        "spans": [
            {
                "name": "checkout.request",
                "required": True,
                "attributes": {
                    "tenant_id": {"type": "string", "required": True, "classification": "identifier", "transformation": "hashed"},
                    "cart_id": {"type": "string", "required": True},
                },
            }
        ],
        "logs": [
            {
                "name": "checkout.failed",
                "required": True,
                "fields": {"reason": {"type": "string", "required": True}},
            }
        ],
        "scenarios": [
            {
                "id": "checkout-triage",
                "question": "Can on-call identify the tenant and failure reason?",
                "requires": [{"kind": "span", "name": "checkout.request", "fields": ["tenant_id"]}],
            }
        ],
    }


def test_contract_diff_reports_pr_review_categories() -> None:
    base = _contract()
    candidate = copy.deepcopy(base)
    candidate["spans"][0]["attributes"].pop("cart_id")
    candidate["spans"][0]["attributes"]["request_id"] = {"type": "string", "required": True}
    candidate["privacy_classifications"]["identifier"] = {"allowed_transformations": ["raw", "hashed"]}
    candidate["spans"][0]["attributes"]["tenant_id"]["transformation"] = "redacted"
    candidate["scenarios"][0]["question"] = "Can on-call identify the tenant, request, and failure reason?"

    report = generate_contract_diff_report(base, candidate)

    assert report["summary"]["new_obligations"] == 1
    assert report["summary"]["removed_obligations"] == 1
    assert report["summary"]["changed_privacy_classifications"] == 2
    assert report["summary"]["changed_diagnosability_claims"] == 1
    assert report["summary"]["pr_attention_required"] is True
    assert {finding["code"] for finding in report["findings"]} == {
        "contract_diff.new_obligation",
        "contract_diff.removed_obligation",
        "contract_diff.privacy_changed",
        "contract_diff.diagnosability_claim_changed",
    }
    assert "Contract-diff PR report" in format_contract_diff_markdown(report)


def test_contract_diff_cli_reports_public_gitlab_fixture(capsys) -> None:
    code = main(
        [
            "contract-diff",
            "--base-contract",
            str(ROOT / "case_studies/gitlab_2017_database_outage/refinement_base_contract.json"),
            "--candidate-contract",
            str(ROOT / "case_studies/gitlab_2017_database_outage/refinement_candidate_weakened_contract.json"),
            "--format",
            "json",
            "--fail-on",
            "never",
        ]
    )
    output = capsys.readouterr().out
    data = json.loads(output)

    assert code == 0
    assert data["summary"]["removed_obligations"] >= 1
    assert "contract_diff.removed_obligation" in data["summary"]["findings_by_code"]
    assert "backup.pg_dump.failed" in output
