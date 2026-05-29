from pathlib import Path

import pytest

from telemetry_contracts.loader import ContractLoadError, load_contract, load_jsonl

ROOT = Path(__file__).resolve().parents[1]


def test_load_json_contract():
    contract = load_contract(ROOT / "examples/contracts/checkout.contract.json")
    assert contract["service"] == "checkout"
    assert contract["spans"][0]["name"] == "checkout.request"


def test_invalid_jsonl_reports_line():
    with pytest.raises(ContractLoadError, match="line 2|:2"):
        load_jsonl(ROOT / "tests/fixtures/bad.jsonl")
