#!/usr/bin/env python3
"""Assemble the static, zero-install browser playground bundle.

The playground runs the *pure-stdlib* engine in the browser under Pyodide with no
backend. To load the package client-side we ship its source as a zip that Pyodide
unpacks into its in-memory filesystem (``pyodide.unpackArchive``). This script:

* zips the ``telemetry_contracts`` package source (``.py`` only, no caches/tests)
  into ``playground/assets/telemetry_contracts.zip``;
* copies a handful of existing repository fixtures into
  ``playground/assets/examples/`` as one-click example datasets;
* writes a deterministic ``playground/assets/examples.json`` index.

Output bytes are deterministic (sorted members, fixed zip metadata) so the bundle
can be committed and a CI smoke test can diff it. Pure stdlib; no network.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PKG = _ROOT / "telemetry_contracts"
_ASSETS = Path(__file__).resolve().parent / "assets"

# Existing repository fixtures surfaced as one-click examples. Each visitor sees
# real findings without typing anything (the datasets were authored as test
# fixtures, not for the playground specifically).
_EXAMPLES = [
    {
        "id": "missing-correlation",
        "title": "Failure with no trace id",
        "description": "An error log that cannot be correlated to its request — the canonical 'why did this fail?' gap.",
        "source": "examples/benchmarks/missing_correlation.events.jsonl",
        "service": None,
    },
    {
        "id": "secret-in-log",
        "title": "Secret leaked into a log",
        "description": "An auth failure log carrying a raw email address — a privacy bug class.",
        "source": "examples/benchmarks/privacy_static.events.jsonl",
        "service": None,
    },
    {
        "id": "checkout-spans",
        "title": "Checkout spans (mixed quality)",
        "description": "Spans and logs from a checkout flow; some carry correlation, some do not.",
        "source": "examples/telemetry/failing.jsonl",
        "service": None,
    },
    {
        "id": "microservices",
        "title": "Well-instrumented microservices",
        "description": "A fuller trace across services — see how a high diagnosability score looks.",
        "source": "examples/microservices/events.jsonl",
        "service": None,
    },
]

# Fixed (non-time-varying) zip metadata so the archive is byte-deterministic.
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def _package_members() -> list[Path]:
    members = [
        path
        for path in _PKG.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    return sorted(members, key=lambda p: p.relative_to(_PKG.parent).as_posix())


def build_bundle() -> dict[str, object]:
    _ASSETS.mkdir(parents=True, exist_ok=True)
    examples_dir = _ASSETS / "examples"
    examples_dir.mkdir(parents=True, exist_ok=True)

    members = _package_members()
    bundle_path = _ASSETS / "telemetry_contracts.zip"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in members:
            arcname = path.relative_to(_PKG.parent).as_posix()
            info = zipfile.ZipInfo(arcname, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())

    index = []
    for example in _EXAMPLES:
        src = _ROOT / example["source"]
        text = src.read_text(encoding="utf-8")
        out_name = f"{example['id']}.jsonl"
        (examples_dir / out_name).write_text(text, encoding="utf-8")
        index.append(
            {
                "id": example["id"],
                "title": example["title"],
                "description": example["description"],
                "file": f"examples/{out_name}",
                "service": example["service"],
            }
        )

    index.sort(key=lambda e: e["id"])
    (_ASSETS / "examples.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return {"bundle": str(bundle_path), "members": len(members), "examples": len(index)}


if __name__ == "__main__":
    result = build_bundle()
    print(json.dumps(result, indent=2, sort_keys=True))
