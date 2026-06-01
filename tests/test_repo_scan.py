import json
from pathlib import Path

import pytest

from telemetry_contracts import cli
from telemetry_contracts.repo_scan import (
    RepoScanError,
    find_telemetry_files,
    parse_repo_target,
    scan_directory,
)

PROJECT = Path(__file__).parent / "fixtures" / "byod" / "project"


def test_parse_repo_target_shorthand():
    assert parse_repo_target("octocat/hello") == "https://github.com/octocat/hello.git"
    assert parse_repo_target("octocat/hello.git") == "https://github.com/octocat/hello.git"
    assert parse_repo_target("github.com/octocat/hello") == "https://github.com/octocat/hello.git"


def test_parse_repo_target_other_hosts():
    assert parse_repo_target("gitlab.com/grp/proj") == "https://gitlab.com/grp/proj.git"
    assert parse_repo_target("bitbucket.org/team/repo") == "https://bitbucket.org/team/repo.git"
    assert parse_repo_target("codeberg.org/u/r") == "https://codeberg.org/u/r.git"
    assert parse_repo_target("gl:grp/proj") == "https://gitlab.com/grp/proj.git"
    assert parse_repo_target("bb:team/repo") == "https://bitbucket.org/team/repo.git"
    assert parse_repo_target("gh:octocat/hello") == "https://github.com/octocat/hello.git"
    # full URLs on any host pass through untouched
    gl = "https://gitlab.com/grp/proj.git"
    assert parse_repo_target(gl) == gl


def test_parse_repo_target_url_passthrough():
    url = "https://github.com/octocat/hello.git"
    assert parse_repo_target(url) == url
    assert parse_repo_target("git@github.com:octocat/hello.git") == "git@github.com:octocat/hello.git"


def test_parse_repo_target_rejects_garbage():
    with pytest.raises(RepoScanError):
        parse_repo_target("not a repo target!!")
    with pytest.raises(RepoScanError):
        parse_repo_target("rm -rf /")


def test_find_telemetry_files_discovers_and_filters():
    files = find_telemetry_files(PROJECT)
    rels = sorted(str(p.relative_to(PROJECT)) for p in files)
    assert "logs/app.logfmt" in rels
    assert "telemetry/events.jsonl" in rels
    # config/manifest json must be excluded
    assert "package.json" not in rels
    assert "src/config.json" not in rels
    # vendored directories are skipped entirely
    assert not any("node_modules" in r for r in rels)


def test_scan_directory_aggregates_across_formats():
    report = scan_directory(PROJECT)
    assert report["schema"] == "telemetry-contracts/repo-scan@1"
    assert report["summary"]["telemetry_files"] == 2
    # logfmt (3) + jsonl (2)
    assert report["summary"]["events"] == 5
    formats = {f["format"] for f in report["files"]}
    assert "logfmt" in formats
    assert "jsonl" in formats
    # every finding is tagged with the file it came from
    assert all("source_file" in f for f in report["findings"])
    sources = {f["source_file"] for f in report["findings"]}
    assert sources.issubset({"logs/app.logfmt", "telemetry/events.jsonl"})


def test_scan_directory_missing_path():
    with pytest.raises(RepoScanError):
        scan_directory(PROJECT / "does-not-exist")


def test_scan_text_is_prioritized_and_actionable():
    from telemetry_contracts.repo_scan import format_scan_text

    report = scan_directory(PROJECT)
    text = format_scan_text(report)
    assert "Top issue types:" in text
    assert "Next steps:" in text
    # errors are listed before warnings
    err_pos = text.index("ERROR telemetry.sensitive_value")
    warn_pos = text.index("WARNING")
    assert err_pos < warn_pos


def test_cli_scan_default_path(monkeypatch, capsys):
    monkeypatch.chdir(PROJECT)
    code = cli.main(["scan", "--format", "json", "--fail-on", "never"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["root"] == "."
    assert payload["summary"]["telemetry_files"] == 2


def test_cli_scan_json(capsys):
    code = cli.main(["scan", "--path", str(PROJECT), "--format", "json", "--fail-on", "never"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["telemetry_files"] == 2


def test_cli_scan_fail_on_error(capsys):
    # the logfmt fixture leaks a bearer token -> at least one error finding
    code = cli.main(["scan", "--path", str(PROJECT), "--format", "text", "--fail-on", "error"])
    capsys.readouterr()
    assert code == 1


def test_cli_scan_repo_bad_target(capsys):
    code = cli.main(["scan-repo", "--repo", "not valid!!", "--fail-on", "never"])
    err = capsys.readouterr().err
    assert code == 2
    assert "repo-scan" in err
