"""One-off generator for benchmarks/ground_truth/curated.jsonl.

Run:  python3 scripts/gen_gold.py
Produces a deterministic, balanced, hand-specified gold set. Every label is
objective ground truth (does the named bug class genuinely hold in the sample?),
independent of what the detector predicts. A small set of "hard" cases encodes
the documented incompleteness/false-positive sources so the benchmark is honest
rather than vacuously perfect.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "benchmarks" / "ground_truth" / "curated.jsonl"

items: list[dict] = []


def add(item_id, bug_class, label, events, rationale, **extra):
    row = {
        "id": item_id,
        "bug_class": bug_class,
        "label": label,
        "events": events,
        "rationale": rationale,
    }
    row.update(extra)
    items.append(row)


SERVICES = ["checkout", "billing", "search", "auth", "gateway", "orders", "users", "payments", "inventory", "shipping"]
OPS = ["handle", "process", "lookup", "commit", "fetch", "render", "validate", "enqueue", "settle", "dispatch"]


# ---------------------------------------------------------------------------
# missing-correlation: failure events with/without a correlation id.
# ---------------------------------------------------------------------------
for i in range(9):
    svc = SERVICES[i]
    add(f"mc-pos-{i:02d}", "missing-correlation", True,
        [{"kind": "event", "name": f"{OPS[i]}_failed", "service": svc, "severity": "error",
          "message": f"{OPS[i]} failed"}],
        "failure event carries no trace_id/request_id/span_id, so it cannot be joined to a trace")
for i in range(9):
    svc = SERVICES[i]
    add(f"mc-neg-{i:02d}", "missing-correlation", False,
        [{"kind": "event", "name": f"{OPS[i]}_failed", "service": svc, "severity": "error",
          "trace_id": f"trace-{i:04d}", "message": f"{OPS[i]} failed"}],
        "failure event carries a recognized trace_id, so the correlation gap is genuinely absent")
# a healthy event without correlation is NOT an instance (bug class is failure-only)
for i in range(2):
    add(f"mc-neg-ok-{i:02d}", "missing-correlation", False,
        [{"kind": "event", "name": f"{OPS[i]}_ok", "service": SERVICES[i], "severity": "info"}],
        "non-failure event: the missing-correlation bug class only applies to failures")
# HARD: correlation id under an unrecognized key -> genuinely present, detector misses the key (FP)
add("mc-hard-altkey", "missing-correlation", False,
    [{"kind": "event", "name": "settle_failed", "service": "payments", "severity": "error",
      "correlationGuid": "abc-123-def"}],
    "a correlation id exists but under an unrecognized field name; the gap is truly absent (documented FP source)")


# ---------------------------------------------------------------------------
# missing-error-evidence: failure with/without error evidence.
# ---------------------------------------------------------------------------
for i in range(9):
    add(f"me-pos-{i:02d}", "missing-error-evidence", True,
        [{"kind": "event", "name": f"{OPS[i]}_failed", "service": SERVICES[i], "severity": "error",
          "trace_id": f"t-{i}"}],
        "failure event carries no error_code/exception/status, so root cause is unrecoverable from the event")
for i in range(9):
    add(f"me-neg-{i:02d}", "missing-error-evidence", False,
        [{"kind": "event", "name": f"{OPS[i]}_failed", "service": SERVICES[i], "severity": "error",
          "trace_id": f"t-{i}", "error_code": "E_TIMEOUT"}],
        "failure event carries an explicit error_code, so error evidence is present")
add("me-neg-exc-00", "missing-error-evidence", False,
    [{"kind": "event", "name": "commit_failed", "service": "billing", "severity": "error",
      "exception": "ValueError"}],
    "failure carries an exception type as error evidence")
# HARD: error detail only in free-text message -> arguably present, detector flags (FP)
add("me-hard-msgonly", "missing-error-evidence", False,
    [{"kind": "event", "name": "fetch_failed", "service": "search", "severity": "error",
      "trace_id": "t-x", "message": "connection refused: ECONNREFUSED upstream:5432"}],
    "the error cause is in the free-text message; structured evidence absent (documented FP source)")


# ---------------------------------------------------------------------------
# missing-duration: spans with/without a duration measure.
# ---------------------------------------------------------------------------
for i in range(9):
    add(f"md-pos-{i:02d}", "missing-duration", True,
        [{"kind": "span", "name": f"{OPS[i]}_span", "service": SERVICES[i], "trace_id": f"t-{i}"}],
        "span carries no duration_ms/latency/elapsed, so operation latency is not computable")
for i in range(9):
    add(f"md-neg-{i:02d}", "missing-duration", False,
        [{"kind": "span", "name": f"{OPS[i]}_span", "service": SERVICES[i], "trace_id": f"t-{i}",
          "duration_ms": 12 + i}],
        "span records duration_ms, so latency is available")
# a plain event without duration is NOT an instance (only spans)
for i in range(2):
    add(f"md-neg-evt-{i:02d}", "missing-duration", False,
        [{"kind": "event", "name": f"{OPS[i]}_log", "service": SERVICES[i]}],
        "non-span event: the missing-duration bug class only applies to spans")


# ---------------------------------------------------------------------------
# sensitive-values: raw secret/PII values vs innocuous values.
# ---------------------------------------------------------------------------
SECRETS = [
    {"user_email": "alice@example.com"},
    {"contact": "bob.jones@corp.example.org"},
    {"authorization": "Bearer abcdefghijklmnopqrstuvwxyz0123456789"},
    {"token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456"},
    {"db_password": "password=Sup3rSecretValue!"},
    {"notify_email": "carol@mail.example.net"},
    {"api_key": "Bearer ZYXWVUTSRQPONMLKJIHGFEDCBA9876543210"},
    {"jwt": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6OTl9.signaturepartHERExyz1234567"},
    {"owner_email": "dave@team.example.com"},
]
for i, payload in enumerate(SECRETS):
    add(f"sv-pos-{i:02d}", "sensitive-values", True,
        [{"kind": "event", "name": "audit", "service": SERVICES[i], **payload}],
        f"field carries a raw secret/PII value matching a conservative pattern ({sorted(payload)[0]})")
INNOCUOUS = [
    {"status": "ok"}, {"count": "42"}, {"region": "us-east-1"}, {"path": "/v1/health"},
    {"method": "GET"}, {"label": "green"}, {"version": "1.4.2"}, {"phase": "warmup"},
    {"node": "worker-3"},
]
for i, payload in enumerate(INNOCUOUS):
    add(f"sv-neg-{i:02d}", "sensitive-values", False,
        [{"kind": "event", "name": "audit", "service": SERVICES[i], **payload}],
        "field value is innocuous and matches no secret/PII pattern")
# HARD: an obfuscated/encoded secret -> genuinely sensitive but detector misses (FN)
add("sv-hard-b64", "sensitive-values", True,
    [{"kind": "event", "name": "audit", "service": "auth",
      "blob": "dXNlcjpwYXNzd29yZEBzZWNyZXQ="}],
    "value is a base64-encoded credential; genuinely sensitive but not matched by raw patterns (documented FN source)")


# ---------------------------------------------------------------------------
# unclassified-sensitive: tenant/customer/account identifiers in the clear.
# ---------------------------------------------------------------------------
SENS_NAMES = ["tenant_id", "customer_id", "account_id", "ssn", "user_email", "session_id", "authorization", "api_key", "secret_token"]
for i, name in enumerate(SENS_NAMES):
    add(f"us-pos-{i:02d}", "unclassified-sensitive", True,
        [{"kind": "event", "name": "request", "service": SERVICES[i], name: f"id-{1000 + i}"}],
        f"field '{name}' names a tenant/customer/account/credential identifier emitted with no privacy classification")
BENIGN_NAMES = ["region", "status", "http_method", "queue_depth", "retry_count", "shard", "zone", "priority", "build_id"]
for i, name in enumerate(BENIGN_NAMES):
    add(f"us-neg-{i:02d}", "unclassified-sensitive", False,
        [{"kind": "event", "name": "request", "service": SERVICES[i], name: f"v-{i}"}],
        f"field '{name}' is operational metadata, not a sensitive/tenant identifier")
# HARD: a genuinely sensitive identifier under a name the (name-based) detector
# does not recognize -> truly sensitive but missed (documented FN source).
add("us-hard-altname", "unclassified-sensitive", True,
    [{"kind": "event", "name": "request", "service": "orders", "org_id": "org-42"}],
    "'org_id' is a tenant-scoped identifier but is not in the recognized name set (documented FN source)")


# ---------------------------------------------------------------------------
# unbounded-cardinality: a metric label with near-unique values across points.
# ---------------------------------------------------------------------------
def metric_points(label_name, label_values, name="http_requests", service="gateway"):
    return [
        {"kind": "metric", "name": name, "service": service, label_name: v, "value": 1}
        for v in label_values
    ]


for i in range(6):
    # 60 points, label takes a (near-)unique value each time -> unbounded.
    add(f"uc-pos-{i:02d}", "unbounded-cardinality", True,
        metric_points("user_id", [f"u{i}-{n}" for n in range(60)], name=f"req_{i}", service=SERVICES[i]),
        "metric label takes a near-unique value across the sampled points (distinct ratio consistent with unbounded cardinality)")
for i in range(6):
    # 60 points, label takes one of 3 bounded values -> bounded.
    add(f"uc-neg-{i:02d}", "unbounded-cardinality", False,
        metric_points("status_code", [["200", "404", "500"][n % 3] for n in range(60)], name=f"req_{i}", service=SERVICES[i]),
        "metric label is bounded (3 distinct values across 60 points)")
# HARD: too few points to trust a high-cardinality verdict -> genuinely unbounded at scale but gated out (FN)
add("uc-hard-smallsample", "unbounded-cardinality", True,
    metric_points("session_id", [f"s-{n}" for n in range(4)], name="rare", service="orders"),
    "session_id is unique per session by construction, so the label is unbounded at scale; the sampled window is below the cardinality-trust threshold (documented FN source)",
    source={"generator": "session_id is unique per session by construction; population cardinality is unbounded though only 4 points were sampled"})


# A handful of second labels for inter-rater reliability (kappa), mostly agreeing.
SECOND = {
    "mc-pos-00": True, "mc-neg-00": False, "mc-hard-altkey": False,
    "me-pos-00": True, "me-neg-00": False, "me-hard-msgonly": False,
    "md-pos-00": True, "md-neg-00": False,
    "sv-pos-00": True, "sv-neg-00": False, "sv-hard-b64": True,
    "us-pos-00": True, "us-neg-00": False,
    "uc-pos-00": True, "uc-neg-00": False, "uc-hard-smallsample": True,
    # one genuine disagreement between labelers
    "us-pos-04": False,
}
for row in items:
    if row["id"] in SECOND:
        row["labeler"] = "primary"
        row["second_label"] = SECOND[row["id"]]

items.sort(key=lambda r: r["id"])
OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as fh:
    fh.write("# telemetry-contracts/gold@1 - curated, hand-labeled ground-truth set\n")
    fh.write("# Each line: one (sample, bug-class) pair with an objective gold label.\n")
    for row in items:
        fh.write(json.dumps(row, sort_keys=True) + "\n")

print(f"wrote {len(items)} gold items to {OUT}")
