# Observability score badge & scorecard

Turn a scan into a shareable, byte-deterministic **observability badge** — the
same kind of badge you already use for build status or coverage — plus a richer
**scorecard** card for your README or dashboards.

Everything here renders from a single scan with no network, no wall-clock, and no
randomness, so the bytes are identical across runs and machines (snapshot-tested).

## Quick start

Emit a shields-style flat badge SVG from any repo or directory:

```bash
python3 -m telemetry_contracts.cli scorecard-badge --path . --format svg --output observability.svg
```

Then reference it in Markdown:

```markdown
![observability](./observability.svg)
```

## Live shields.io endpoint

Instead of committing an SVG, publish a shields.io *endpoint* JSON and let
shields render the badge for you:

```bash
python3 -m telemetry_contracts.cli scorecard-badge --path . --format shields-json --output observability.json
```

The payload is the shields endpoint schema:

```json
{
  "schemaVersion": 1,
  "label": "observability",
  "message": "93/100",
  "color": "#4c1"
}
```

Host that JSON (e.g. as a raw file in your repo) and point shields at it:

```markdown
![observability](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/OWNER/REPO/main/observability.json)
```

The color follows the diagnosability score: green ≥ 90, yellow-green ≥ 75,
amber bands below that, red when low, and grey when no telemetry is discovered.

## Scorecard card

For a fuller summary (score plus the top gaps and the verdict), render the
scorecard SVG:

```bash
python3 -m telemetry_contracts.cli scorecard-badge --path . --format scorecard --output observability-card.svg
```

## Rendering from an existing report

If you already produced a `ci-report` JSON (see the GitHub Action docs), render
the badge straight from it without re-scanning:

```bash
python3 -m telemetry_contracts.cli ci-report --path . --output report.json
python3 -m telemetry_contracts.cli scorecard-badge --report report.json --format svg --output observability.svg
```

## Options

- `--path DIR` — scan a directory/repository (mutually exclusive with `--report`).
- `--report FILE` — render from a prior `ci-report` JSON.
- `--format {svg,scorecard,shields-json}` — badge SVG (default), scorecard card, or shields endpoint JSON.
- `--label TEXT` — badge label (default `observability`).
- `--service NAME` — restrict to a single service.
- `--max-files N` — cap scanned files (default 300).
- `--output FILE` — write to a file instead of stdout.

## Python API

```python
from telemetry_contracts import (
    analyze_for_ci,
    render_badge_svg,
    render_scorecard_svg,
    shields_endpoint_json,
)

report = analyze_for_ci(".")
svg = render_badge_svg(report["diagnosability_score"])
endpoint = shields_endpoint_json(report["diagnosability_score"])
card = render_scorecard_svg(report)
```
