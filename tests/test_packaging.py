from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".pytest_cache" / "package-smoke"


def test_pyproject_has_pypi_quality_metadata_and_long_description():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = pyproject["project"]
    assert project["readme"] == "README.md"
    assert (ROOT / project["readme"]).read_text().startswith("# Telemetry Contracts")
    assert "License :: OSI Approved :: MIT License" in project["classifiers"]
    assert "Environment :: Console" in project["classifiers"]
    assert project["urls"]["Repository"].endswith("telemetry-contract-semantics")
    assert "telemetry-contracts" in pyproject["project"]["scripts"]


def test_wheel_and_editable_console_script_smoke():
    if CACHE.exists():
        shutil.rmtree(CACHE)
    wheels = CACHE / "wheels"
    wheels.mkdir(parents=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "--wheel-dir", str(wheels), "--quiet"],
        cwd=ROOT,
        check=True,
        timeout=120,
    )
    wheel = next(wheels.glob("telemetry_contracts-*.whl"))
    for mode, install_target in (("wheel", str(wheel)), ("editable", "-e")):
        venv = CACHE / f"venv-{mode}"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], cwd=ROOT, check=True, timeout=120)
        python = venv / ("Scripts" if os.name == "nt" else "bin") / "python"
        script = venv / ("Scripts" if os.name == "nt" else "bin") / "telemetry-contracts"
        install_cmd = [str(python), "-m", "pip", "install", "--quiet"]
        install_cmd.extend([install_target, str(ROOT)] if install_target == "-e" else [install_target])
        subprocess.run(install_cmd, cwd=ROOT, check=True, timeout=120)
        result = subprocess.run(
            [str(script), "lint-contract", "--contract", "examples/contracts/checkout.contract.json"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        assert "OK: no findings" in result.stdout or '"findings": []' in result.stdout
