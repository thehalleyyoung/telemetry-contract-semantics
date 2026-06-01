import json
from pathlib import Path

from telemetry_contracts.cli import main
from telemetry_contracts.taxonomy import format_taxonomy_markdown, summarize_findings, taxonomy_document

ROOT = Path(__file__).resolve().parents[1]


def test_taxonomy_document_is_machine_readable_and_ci_mapped():
    document = taxonomy_document()

    assert document["schema"] == "docs/finding_taxonomy.schema.json"
    assert document["summary"]["rules"] == len(document["rules"])
    assert document["summary"]["categories"]["diagnosability"] >= 1
    for rule in document["rules"]:
        assert rule["formal_clause"]
        assert rule["ci"]["sarif_level"] == rule["sarif_level"]
        assert "code" in rule["ci"]["baseline_key_fields"]


def test_taxonomy_carries_bug_class_guarantee_metadata():
    from telemetry_contracts.bug_classes import (
        BUG_CLASS_IDS,
        CODE_TO_BUG_CLASS,
        soundness_rows,
    )

    document = taxonomy_document()

    # The bug-class guarantee statements are embedded verbatim from the single
    # source of truth so docs/paper/tool can never drift.
    assert document["bug_classes"] == soundness_rows()

    # Every rule carries a bug_class field that agrees with the SoT mapping.
    for rule in document["rules"]:
        assert "bug_class" in rule
        assert rule["bug_class"] == CODE_TO_BUG_CLASS.get(rule["code"])

    # Every bug class is witnessed by at least one taxonomy rule.
    witnessed = {r["bug_class"] for r in document["rules"] if r["bug_class"]}
    assert witnessed == set(BUG_CLASS_IDS)



    generated = taxonomy_document()
    checked_in = json.loads((ROOT / "docs/finding_taxonomy.json").read_text(encoding="utf-8"))

    assert checked_in == generated


def test_taxonomy_summarizes_benchmark_findings():
    summary = summarize_findings([ROOT / "reports/current_impact.json"])

    assert summary["summary"]["findings"] == 74
    assert summary["summary"]["unknown_codes"] == []
    assert summary["summary"]["by_formal_clause"]["SAT.allowed-values"] == 4
    assert summary["summary"]["by_category"]["privacy-security"] == 26
    assert summary["summary"]["by_formal_clause"]["HYP.pii-non-disclosure"] == 4
    assert summary["summary"]["by_formal_clause"]["OTLP.dropped-evidence"] == 2
    assert summary["summary"]["by_formal_clause"]["SAT.temporal-response"] == 1


def test_taxonomy_markdown_includes_observed_coverage():
    report = taxonomy_document()
    report["observed_findings"] = summarize_findings([ROOT / "reports/current_impact.json"])
    markdown = format_taxonomy_markdown(report)

    assert "# Finding taxonomy" in markdown
    assert "Observed finding coverage" in markdown
    assert "STATIC.raw-sensitive-log" in markdown


def test_cli_taxonomy_json_and_markdown(capsys):
    code = main(["taxonomy", "--findings", str(ROOT / "reports/current_impact.json"), "--format", "json"])
    output = capsys.readouterr().out
    data = json.loads(output)

    assert code == 0
    assert data["observed_findings"]["summary"]["unknown_codes"] == []
    assert data["observed_findings"]["summary"]["by_code"]["static.secret_logging"] == 5
    assert data["observed_findings"]["summary"]["by_code"]["static.pii_logging"] == 3

    code = main(["taxonomy", "--format", "markdown"])
    output = capsys.readouterr().out
    assert code == 0
    assert "| Code | Category | Severity | Formal clause |" in output
