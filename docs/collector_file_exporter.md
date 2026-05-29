# Vendor-neutral OpenTelemetry Collector file-exporter workflow

This workflow validates real collector exports without depending on a telemetry vendor or backend. It uses the Collector `file` exporter to write OTLP JSON locally, then runs deterministic importer, analysis, validation, and preservation checks.

## Minimal collector shape

```yaml
receivers:
  otlp:
    protocols:
      grpc:
      http:

processors:
  batch:

exporters:
  file/contracts-json:
    path: ./collector-export.otlp.json
    format: json

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [file/contracts-json]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [file/contracts-json]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [file/contracts-json]
```

If your Collector writes one OTLP JSON object per line, pass `--input-format jsonl` to the commands below.

## CI smoke commands

```bash
python3 -m telemetry_contracts.cli import-otlp \
  --input collector-export.otlp.json \
  --output collector-export.events.jsonl \
  --diagnostics-output collector-export.diagnostics.json

python3 -m telemetry_contracts.cli analyze-collector-export \
  --input collector-export.otlp.json \
  --format markdown

python3 -m telemetry_contracts.cli validate \
  --contract service.contract.json \
  --events collector-export.events.jsonl \
  --strict --format json --fail-on never
```

The checked-in smoke fixture `examples/otlp/collector_coverage_all_signals.otlp.json` exercises spans, logs, sums, gauges, histograms, exponential histograms, summaries, exemplars, links, span events, resource/scope metadata, temporality, dropped-evidence diagnostics, unsupported-feature diagnostics, and PII/cardinality analysis inputs. The Make target `make otlp-import collector-analysis collector-preservation` runs the vendor-neutral fixture without a collector binary.

## Round-trip differential testing

Use `export-otlp` when changing importer semantics. It converts normalized telemetry-contracts JSONL back to collector-style OTLP JSON so the import path can be tested for stable signal names, kinds, trace IDs, exemplars, and resource/scope metadata:

```bash
python3 -m telemetry_contracts.cli export-otlp \
  --events examples/otlp/collector_mixed_signals.events.jsonl \
  --output roundtrip.otlp.json
python3 -m telemetry_contracts.cli import-otlp \
  --input roundtrip.otlp.json \
  --output roundtrip.events.jsonl
```

## Collector-pipeline preservation

`examples/otlp/collector_pipeline_*` demonstrates a contract-scoped preservation check for declared redaction, sampling, aggregation, and routing steps. It proves only that the supplied finite before/after artifacts preserve the selected contract and scenario obligations; it does not certify a production collector configuration.
