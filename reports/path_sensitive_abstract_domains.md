# Abstract telemetry domains

- Domains: 6
- Events: 4
- String bound: 5

## bounded_strings

- Join: set union while cardinality <= bound; otherwise many
- Widening: collapse to many after the configured bound
- Limitations: tracks exact finite fixture strings only, not all production values

```json
{
  "log:checkout.fallback.fallback_reason": [
    "processor-timeout"
  ],
  "log:checkout.fallback.trace_id": [
    "t1"
  ],
  "span:checkout.exception.exception.type": [
    "TimeoutError"
  ],
  "span:checkout.exception.trace_id": [
    "t2"
  ],
  "span:checkout.request.experiment_id": [
    "exp-42"
  ],
  "span:checkout.request.feature_flag": [
    "new-payment"
  ],
  "span:checkout.request.trace_id": [
    "t1"
  ],
  "span:payment.retry.fallback_reason": [
    "processor-timeout"
  ],
  "span:payment.retry.trace_id": [
    "t1"
  ]
}
```

## attribute_presence

- Join: must=intersection, may=union
- Widening: drop per-event provenance and keep field sets
- Limitations: presence is fixture-relative and path-insensitive unless paired with path_feasibility

```json
{
  "log:checkout.fallback": {
    "may": [],
    "missing_declared": [],
    "must": [
      "fallback_reason",
      "trace_id"
    ],
    "observed_extra": []
  },
  "span:checkout.exception": {
    "may": [],
    "missing_declared": [],
    "must": [
      "exception.type",
      "retryable",
      "trace_id"
    ],
    "observed_extra": []
  },
  "span:checkout.request": {
    "may": [
      "experiment_id"
    ],
    "missing_declared": [],
    "must": [
      "feature_flag",
      "trace_id"
    ],
    "observed_extra": [
      "experiment_id"
    ]
  },
  "span:payment.retry": {
    "may": [
      "fallback_reason"
    ],
    "missing_declared": [],
    "must": [
      "fallback",
      "retry_count",
      "trace_id"
    ],
    "observed_extra": [
      "fallback_reason"
    ]
  }
}
```

## severity

- Join: maximum severity by operational order
- Widening: collapse unknown labels to top=FATAL
- Limitations: custom backend severity scales are normalized to common labels only

```json
{
  "checkout.fallback": {
    "join": "WARN",
    "observed": [
      "WARN"
    ]
  }
}
```

## units

- Join: equal units stay exact; conflicts join to unit-set
- Widening: collapse incompatible growing unit sets to mixed
- Limitations: does not perform physical dimensional analysis beyond declared strings

```json
{}
```

## privacy_class

- Join: least upper bound is the most restrictive class present
- Widening: unknown or conflicting classes widen to sensitive
- Limitations: classification depends on explicit contract annotations

```json
{}
```

## path_feasibility

- Join: feasible dominates unknown; infeasible only when explicitly contradicted
- Widening: merge loop/retry paths by condition id and bounded witnesses
- Limitations: prototype is condition-sensitive but not a full control-flow analyzer

```json
{
  "span:checkout.request.conditional[0]": {
    "condition": {
      "equals": "new-payment",
      "field": "feature_flag"
    },
    "state": "feasible",
    "witness_events": [
      1
    ]
  },
  "span:payment.retry.conditional[0]": {
    "condition": {
      "equals": true,
      "field": "fallback"
    },
    "state": "feasible",
    "witness_events": [
      2
    ]
  }
}
```

