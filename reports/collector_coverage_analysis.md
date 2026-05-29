# Collector export analysis

- Events: 7
- Diagnostics: 4
- Invalidating diagnostics: 3
- Collector risk count: 10
- Dropped evidence: 2
- Cardinality risks: 4
- PII/secret risks: 1
- Unsupported features: 2
- Unknown schemas: 1
- Missing temporality: 0

## Temporality

- Counts: `{"AGGREGATION_TEMPORALITY_CUMULATIVE": 1, "AGGREGATION_TEMPORALITY_DELTA": 2}`
- Missing for metrics: `[]`

## Dropped evidence

- `{"code": "otlp.dropped_evidence", "details": {"count": 1, "field": "droppedLinksCount"}, "invalidates_contract_claim": true, "message": "droppedLinksCount=1 indicates collector/exporter loss", "path": "$.resourceSpans[0].scopeSpans[0].spans[0].droppedLinksCount", "severity": "warning"}`
- `{"code": "otlp.dropped_evidence", "details": {"count": 1, "field": "droppedAttributesCount"}, "invalidates_contract_claim": true, "message": "droppedAttributesCount=1 indicates collector/exporter loss", "path": "$.resourceLogs[0].scopeLogs[0].logRecords[0].droppedAttributesCount", "severity": "warning"}`

## Cardinality risks

- `{"distinct_values": 1, "field": "cart_id", "risk": "high_cardinality_label"}`
- `{"distinct_values": 1, "field": "request_id", "risk": "high_cardinality_label"}`
- `{"distinct_values": 1, "field": "session_id", "risk": "high_cardinality_label"}`
- `{"distinct_values": 5, "field": "tenant_id", "risk": "high_cardinality_label"}`

## PII/secret risks

- `{"event_index": 6, "field": "email", "kind": "log", "risk": "sensitive_value_pattern", "value_preview": "user\u2026.com"}`

## Unknown schemas

- `{"events": 5, "schema_url": "https://vendor.example/schemas/private"}`

## Unsupported OTLP features

- `{"code": "otlp.unsupported_metric", "invalidates_contract_claim": true, "message": "unsupported metric payload for checkout.unsupported", "path": "$.resourceMetrics[0].scopeMetrics[0].metrics[5]", "severity": "warning"}`
- `{"code": "otlp.unsupported_top_level", "invalidates_contract_claim": false, "message": "ignored unsupported top-level OTLP field 'partialSuccess'", "path": "$.partialSuccess", "severity": "info"}`

## Limitations

- Cardinality is estimated over the supplied finite export, not backend-wide production series.
- PII/secret risk checks are heuristic field-name and value-pattern checks for triage.
- Unsupported-feature diagnostics bound the validity of contract claims made from this export.

