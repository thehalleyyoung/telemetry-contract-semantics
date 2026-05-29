# Current public-code static pattern case study

This disclosure-safe case study lives in this public repository and is cited by immutable path rather than copied from a third-party project. It exercises four static telemetry review patterns: missing trace/request correlation on an error log, high-cardinality metric labels, unsafe raw payload logging, and an incomplete error span that lacks exception recording/status/remediation evidence.

The fixture is not a vulnerability report. It is a bounded public-code regression input for `telemetry-contracts static`.
