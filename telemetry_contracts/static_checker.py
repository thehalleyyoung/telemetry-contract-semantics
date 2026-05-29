from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .findings import Finding

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".cs", ".rb", ".rs"}
SENSITIVE_NAMES = re.compile(r"(?i)(password|passwd|pwd|token|secret|authorization|auth[_-]?token|cookie|api[_-]?key|session[_-]?id|email|phone|tenant[_-]?id|raw[_-]?payload|payload[_-]?preview)")
SECRET_ONLY_NAMES = re.compile(r"(?i)(password|passwd|pwd|token|secret|authorization|auth[_-]?token|cookie|api[_-]?key|session[_-]?id)")
LOG_CALL = re.compile(r"(?i)\b(console\.(?:log|error|warn)|logger\.(?:error|warning|warn|info|debug)|log\.(?:Error|Warn|Info|Debug|Printf|Println)|print|printf)\b")
ERROR_WORDS = re.compile(r"(?i)(error|exception|failed|failure|unauthori[sz]ed|invalid credentials|invalid password|timeout)")
METRIC_WORDS = re.compile(r"(?i)(counter|histogram|gauge|metric|labels?|tags?|attributes?)")
HIGH_CARD_NAMES = re.compile(r"(?i)(user(name)?|email|ip|url|path|session|cookie|cart|order|request|trace)")
EXCEPTION_WORDS = re.compile(r"(?i)(except|catch|Exception|Throwable|Error\b|err\b|ex\b|exception)")


@dataclass
class SourceSpan:
    path: Path
    line: int
    column: int = 1
    end_line: int | None = None
    end_column: int | None = None

    def location(self) -> str:
        end = f"-{self.end_line or self.line}:{self.end_column or self.column}" if self.end_line or self.end_column else ""
        return f"{self.path}:{self.line}:{self.column}{end}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line or self.line,
            "end_column": self.end_column or self.column,
        }


@dataclass
class Observation:
    kind: str
    name: str | None
    span: SourceSpan
    api: str
    attributes: set[str] = field(default_factory=set)
    details: dict[str, Any] = field(default_factory=dict)


def expected_names(contract: dict[str, Any]) -> dict[str, list[str]]:
    configured = contract.get("static_expectations") or {}
    names: dict[str, list[str]] = {"spans": [], "metrics": [], "logs": []}
    for section in names:
        explicit = configured.get(section)
        if isinstance(explicit, list):
            names[section].extend(str(item) for item in explicit)
        else:
            names[section].extend(str(item.get("name")) for item in contract.get(section, []) if isinstance(item, dict) and item.get("required", True) and item.get("name"))
    return names


def check_sources(contract: dict[str, Any], source_paths: Iterable[str | Path]) -> list[Finding]:
    files = _collect_files(source_paths)
    findings: list[Finding] = []
    observations: list[Observation] = []
    texts: list[tuple[Path, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        texts.append((path, text))
        observations.extend(_extract_observations(path, text))

    observed_names = {
        "spans": {item.name for item in observations if item.kind == "span" and item.name},
        "metrics": {item.name for item in observations if item.kind == "metric" and item.name},
        "logs": {item.name for item in observations if item.kind == "log" and item.name},
    }
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for name in expected_names(contract)[section]:
            if name not in observed_names[section]:
                findings.append(Finding(
                    "error",
                    "static.missing_instrumentation",
                    f"expected {kind} name '{name}' was not found in AST/source telemetry API usage",
                    "source",
                    f"$.static_expectations.{section}",
                    None,
                    {"name": name, "obligation": {"kind": kind, "name": name}},
                ))
    for path, text in texts:
        findings.extend(_scan_source(path, text, contract, observations))
    findings.extend(_check_static_api_obligations(contract, observations))
    if not files:
        findings.append(Finding("warning", "static.no_sources", "no source files were checked", "source"))
    return findings


def _extract_observations(path: Path, text: str) -> list[Observation]:
    if path.suffix == ".py":
        return _extract_python_observations(path, text)
    return _extract_text_observations(path, text)


def _extract_python_observations(path: Path, text: str) -> list[Observation]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return _extract_text_observations(path, text)
    constants: dict[str, str] = {}
    observations: list[Observation] = []
    span_vars: dict[str, Observation] = {}

    class Visitor(ast.NodeVisitor):
        def visit_Assign(self, node: ast.Assign) -> Any:
            value = _literal_eval(node.value, constants)
            if value is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = value
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
            value = _literal_eval(node.value, constants) if node.value is not None else None
            if value is not None and isinstance(node.target, ast.Name):
                constants[node.target.id] = value
            self.generic_visit(node)

        def visit_With(self, node: ast.With) -> Any:
            for item in node.items:
                call = item.context_expr if isinstance(item.context_expr, ast.Call) else None
                name = _call_string_arg(call, constants) if call else None
                api = _call_name(call.func) if call else "with"
                if call and name and _looks_like_span_api(api):
                    obs = Observation("span", name, _span(path, call), api)
                    observations.append(obs)
                    if isinstance(item.optional_vars, ast.Name):
                        span_vars[item.optional_vars.id] = obs
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> Any:
            api = _call_name(node.func)
            name = _call_string_arg(node, constants)
            attrs = _call_attributes(node, constants)
            if name and api.endswith(("get_tracer", "getTracer", "TracerProvider.get")):
                observations.append(Observation("tracer", name, _span(path, node), api))
            elif name and api.endswith(("get_meter", "getMeter", "MeterProvider.get")):
                observations.append(Observation("meter", name, _span(path, node), api))
            elif name and _looks_like_span_api(api):
                obs = Observation("span", name, _span(path, node), api, set(attrs))
                observations.append(obs)
            elif name and _looks_like_metric_api(api):
                observations.append(Observation("metric", name, _span(path, node), api, set(attrs), _metric_details(api, node, constants)))
            elif _looks_like_log_api(api):
                log_name = _log_name_from_call(node, constants) or name
                observations.append(Observation("log", log_name, _span(path, node), api, set(attrs), {"line": _source_segment(text, node)}))
            if _is_set_attribute(api) and len(node.args) >= 1:
                attr = _literal_eval(node.args[0], constants)
                receiver = _receiver_name(node.func)
                if attr and receiver in span_vars:
                    span_vars[receiver].attributes.add(attr)
            if _is_record_exception(api):
                receiver = _receiver_name(node.func)
                if receiver in span_vars:
                    span_vars[receiver].details["records_exception"] = True
            if _is_set_status(api):
                receiver = _receiver_name(node.func)
                if receiver in span_vars:
                    span_vars[receiver].details["sets_error_status"] = _status_is_error(node, constants)
            self.generic_visit(node)

    Visitor().visit(tree)
    return observations


def _extract_text_observations(path: Path, text: str) -> list[Observation]:
    constants = _text_constants(text)
    observations: list[Observation] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "#", "*")):
            continue
        resolved = _resolve_text_fragments(stripped, constants)
        col = max(1, line.find(stripped) + 1)
        span = SourceSpan(path, line_number, col, line_number, col + len(stripped))
        lower = stripped.lower()
        for value in resolved:
            if "get_tracer" in lower or "gettracer" in lower:
                observations.append(Observation("tracer", value, span, "text.tracer"))
            if "get_meter" in lower or "getmeter" in lower:
                observations.append(Observation("meter", value, span, "text.meter"))
            if _line_looks_like_span(lower):
                observations.append(Observation("span", value, span, "text.span"))
            if _line_looks_like_metric(lower):
                observations.append(Observation("metric", value, span, "text.metric", _attributes_from_text(stripped)))
            if _line_looks_like_log(lower):
                observations.append(Observation("log", value, span, "text.log", _attributes_from_text(stripped), {"line": stripped}))
        if _line_looks_like_log(lower):
            event_name = _extract_named_field(stripped, "event_name") or _extract_named_field(stripped, "eventName")
            observations.append(Observation("log", event_name, span, "text.log", _attributes_from_text(stripped), {"line": stripped}))
    return observations


def _scan_source(path: Path, text: str, contract: dict[str, Any], observations: list[Observation]) -> list[Finding]:
    findings: list[Finding] = []
    rules = contract.get("static_rules") if isinstance(contract.get("static_rules"), dict) else {}
    require_correlation = bool(rules.get("require_correlation_on_error_logs"))
    detect_unbounded_labels = bool(rules.get("detect_unbounded_labels"))
    correlation_fields = [str(item) for item in rules.get("correlation_fields", ["trace_id", "traceId", "request_id", "requestId", "span_id"])]
    path_observations = [item for item in observations if item.span.path == path]
    observed_log_lines = {item.span.line for item in path_observations if item.kind == "log"}
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("//", "#", "*")):
            continue
        column = max(1, line.find(stripped) + 1)
        span = SourceSpan(path, line_number, column, line_number, column + len(stripped))
        line_observations = [item for item in path_observations if item.span.line == line_number]
        if line_number in observed_log_lines and SECRET_ONLY_NAMES.search(stripped):
            findings.append(Finding("error", "static.secret_logging", "logging statement appears to include a credential, token, cookie, or other sensitive value", span.location(), None, None, {"line": _redact_line(stripped), "source_span": span.to_dict()}))
        if require_correlation and line_number in observed_log_lines and ERROR_WORDS.search(stripped):
            attrs = {attr for obs in line_observations for attr in obs.attributes}
            if not any(field in stripped or field in attrs for field in correlation_fields):
                findings.append(Finding("warning", "static.missing_correlation", "error log may be missing trace/request correlation fields", span.location(), None, None, {"line": _redact_line(stripped), "expected_any": correlation_fields, "source_span": span.to_dict()}))
        if detect_unbounded_labels and METRIC_WORDS.search(stripped) and HIGH_CARD_NAMES.search(stripped) and not re.search(r"(?i)(bucket|hash|redact|cardinality|max)", stripped):
            findings.append(Finding("warning", "static.unbounded_label", "metric/tag code appears to use a high-cardinality or user-controlled label without bucketing", span.location(), None, None, {"line": _redact_line(stripped), "source_span": span.to_dict()}))
    return findings


def _check_static_api_obligations(contract: dict[str, Any], observations: list[Observation]) -> list[Finding]:
    rules = contract.get("static_rules") if isinstance(contract.get("static_rules"), dict) else {}
    findings: list[Finding] = []
    findings.extend(_check_tracer_meter_names(rules, observations))
    findings.extend(_check_metric_metadata(contract, rules, observations))
    findings.extend(_check_required_source_attributes(contract, rules, observations))
    if not rules.get("require_error_span_observability"):
        return findings
    error_spans = _contract_error_spans(contract)
    by_name: dict[str, list[Observation]] = {}
    for obs in observations:
        if obs.kind == "span" and obs.name in error_spans:
            by_name.setdefault(str(obs.name), []).append(obs)
    for name, span_observations in by_name.items():
        obs = span_observations[0]
        merged_attributes = {attr for item in span_observations for attr in item.attributes}
        records_exception = any(item.details.get("records_exception") for item in span_observations)
        sets_error_status = any(item.details.get("sets_error_status") for item in span_observations)
        required = error_spans[name]
        if not records_exception:
            findings.append(_api_finding("static.missing_exception_recording", "error span does not record the caught exception", obs, required))
        if not sets_error_status:
            findings.append(_api_finding("static.missing_error_status", "error span does not set OpenTelemetry ERROR status", obs, required))
        for field_name in sorted(required & {"remediation_hint", "remediation", "retryable"}):
            if field_name not in merged_attributes:
                code = "static.missing_remediation_field" if field_name.startswith("remediation") else "static.inconsistent_retryability"
                message = f"error span does not attach required '{field_name}' evidence"
                findings.append(_api_finding(code, message, obs, {field_name}))
    return findings


def _check_tracer_meter_names(rules: dict[str, Any], observations: list[Observation]) -> list[Finding]:
    findings: list[Finding] = []
    for kind, code, key in (
        ("tracer", "static.missing_tracer_name", "expected_tracer_names"),
        ("meter", "static.missing_meter_name", "expected_meter_names"),
    ):
        expected = {str(item) for item in rules.get(key, []) if str(item)}
        observed = {item.name for item in observations if item.kind == kind and item.name}
        for name in sorted(expected - observed):
            findings.append(Finding("warning", code, f"expected OpenTelemetry {kind} name '{name}' was not found in source", "source", None, None, {"name": name, "obligation": {"kind": kind, "name": name}}))
    return findings


def _check_metric_metadata(contract: dict[str, Any], rules: dict[str, Any], observations: list[Observation]) -> list[Finding]:
    if not rules.get("require_metric_metadata"):
        return []
    findings: list[Finding] = []
    observed = {item.name: item for item in observations if item.kind == "metric" and item.name}
    for metric in contract.get("metrics", []):
        if not isinstance(metric, dict) or not metric.get("name"):
            continue
        obs = observed.get(str(metric["name"]))
        if obs is None:
            continue
        for field_name, code in (("unit", "static.metric_unit"), ("description", "static.metric_description")):
            if metric.get(field_name) and not obs.details.get(field_name):
                findings.append(_api_finding(code, f"metric '{metric['name']}' is missing {field_name} in source API usage", obs, {field_name}))
    return findings


def _check_required_source_attributes(contract: dict[str, Any], rules: dict[str, Any], observations: list[Observation]) -> list[Finding]:
    if not rules.get("require_semconv_attributes"):
        return []
    findings: list[Finding] = []
    observed_by_key: dict[tuple[str, str], list[Observation]] = {}
    for item in observations:
        if item.name:
            observed_by_key.setdefault((item.kind, str(item.name)), []).append(item)
    for section, kind in (("spans", "span"), ("metrics", "metric"), ("logs", "log")):
        for spec in contract.get(section, []):
            if not isinstance(spec, dict) or not spec.get("name"):
                continue
            matches = observed_by_key.get((kind, str(spec["name"])), [])
            if not matches:
                continue
            obs = matches[0]
            observed_attrs = {attr for item in matches for attr in item.attributes}
            required_attrs = {name for name, field_spec in _contract_fields(spec).items() if "." in name and (not isinstance(field_spec, dict) or field_spec.get("required", True))}
            missing = required_attrs - observed_attrs
            for attr in sorted(missing):
                findings.append(_api_finding("static.missing_semconv_attribute", f"{kind} '{spec['name']}' source instrumentation does not attach semantic attribute '{attr}'", obs, {attr}))
    return findings


def _contract_fields(spec: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for key in ("fields", "attributes", "tags"):
        value = spec.get(key)
        if isinstance(value, dict):
            merged.update(value)
    return merged


def _api_finding(code: str, message: str, obs: Observation, obligation_fields: set[str]) -> Finding:
    return Finding("warning", code, message, obs.span.location(), None, None, {"source_span": obs.span.to_dict(), "obligation": {"kind": obs.kind, "name": obs.name, "fields": sorted(obligation_fields)}, "api": obs.api})


def _contract_error_spans(contract: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for span in contract.get("spans", []):
        if not isinstance(span, dict) or not span.get("name"):
            continue
        fields = span.get("fields") if isinstance(span.get("fields"), dict) else {}
        conditionals = span.get("conditional_requirements") if isinstance(span.get("conditional_requirements"), list) else []
        required = {str(name) for name, spec in fields.items() if name in {"error_code", "exception.type", "remediation_hint", "remediation", "retryable"} and (not isinstance(spec, dict) or spec.get("required", True))}
        for req in conditionals:
            if isinstance(req, dict) and isinstance(req.get("then"), dict):
                required.update(str(item) for item in req["then"].get("fields", []) if item in {"remediation_hint", "remediation", "retryable"})
        if required:
            result[str(span["name"])] = required
    return result


def _literal_eval(node: ast.AST | None, constants: dict[str, str]) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float)):
        return str(node.value)
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_eval(node.left, constants)
        right = _literal_eval(node.right, constants)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                pieces.append(str(value.value))
            elif isinstance(value, ast.FormattedValue):
                resolved = _literal_eval(value.value, constants)
                if resolved is None:
                    return None
                pieces.append(resolved)
        return "".join(pieces)
    if isinstance(node, ast.Call):
        return _call_string_arg(node, constants)
    return None


def _call_string_arg(node: ast.Call | None, constants: dict[str, str]) -> str | None:
    if node is None:
        return None
    for arg in node.args:
        value = _literal_eval(arg, constants)
        if value is not None:
            return value
    for keyword in node.keywords:
        if keyword.arg in {"name", "event_name", "unit", "description"}:
            value = _literal_eval(keyword.value, constants)
            if value is not None:
                return value
    return None


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Attribute):
        prefix = _call_name(func.value)
        return f"{prefix}.{func.attr}" if prefix else func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _receiver_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id
    return None


def _call_attributes(node: ast.Call, constants: dict[str, str]) -> set[str]:
    attrs: set[str] = set()
    for keyword in node.keywords:
        if keyword.arg in {"attributes", "attribute", "attrs", "tags", "labels", "extra"}:
            attrs.update(_keys_from_node(keyword.value, constants))
    for arg in node.args[1:]:
        attrs.update(_keys_from_node(arg, constants))
    return attrs


def _keys_from_node(node: ast.AST, constants: dict[str, str]) -> set[str]:
    if isinstance(node, ast.Dict):
        return {value for key in node.keys if (value := _literal_eval(key, constants)) is not None}
    return set()


def _log_name_from_call(node: ast.Call, constants: dict[str, str]) -> str | None:
    attrs = _call_attributes(node, constants)
    for keyword in node.keywords:
        if keyword.arg == "extra" and isinstance(keyword.value, ast.Dict):
            for key, value in zip(keyword.value.keys, keyword.value.values):
                k = _literal_eval(key, constants)
                if k in {"event_name", "eventName", "name"}:
                    return _literal_eval(value, constants)
    for attr in attrs:
        if attr in {"event_name", "eventName"}:
            return None
    message = _literal_eval(node.args[0], constants) if node.args else None
    if message:
        token = message.split()[0]
        if "." in token and re.match(r"^[A-Za-z0-9_.-]+$", token):
            return token
    return None


def _metric_details(api: str, node: ast.Call, constants: dict[str, str]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    for keyword in node.keywords:
        if keyword.arg in {"unit", "description"}:
            details[keyword.arg] = _literal_eval(keyword.value, constants)
    details["instrument"] = api.rsplit(".", 1)[-1]
    return details


def _span(path: Path, node: ast.AST) -> SourceSpan:
    return SourceSpan(path, getattr(node, "lineno", 1), getattr(node, "col_offset", 0) + 1, getattr(node, "end_lineno", None), (getattr(node, "end_col_offset", 0) or 0) + 1 if getattr(node, "end_col_offset", None) is not None else None)


def _source_segment(text: str, node: ast.AST) -> str:
    return (ast.get_source_segment(text, node) or "")[:240]


def _looks_like_span_api(api: str) -> bool:
    return any(part in api for part in ("start_as_current_span", "startSpan", "start_span", "span")) and not _is_set_attribute(api)


def _looks_like_metric_api(api: str) -> bool:
    return any(part in api.lower() for part in ("counter", "histogram", "gauge", "meter", "metric"))


def _looks_like_log_api(api: str) -> bool:
    return bool(LOG_CALL.search(api)) or api.lower().endswith((".error", ".warning", ".warn", ".info", ".debug"))


def _is_set_attribute(api: str) -> bool:
    return api.endswith(("set_attribute", "setAttribute", "SetAttribute"))


def _is_record_exception(api: str) -> bool:
    return api.endswith(("record_exception", "recordException", "RecordException"))


def _is_set_status(api: str) -> bool:
    return api.endswith(("set_status", "setStatus", "SetStatus"))


def _status_is_error(node: ast.Call, constants: dict[str, str]) -> bool:
    text = " ".join(filter(None, [_literal_eval(arg, constants) for arg in node.args]))
    text += " " + " ".join(_call_name(keyword.value) for keyword in node.keywords)
    text += " " + " ".join(ast.unparse(arg) for arg in node.args)
    return "ERROR" in text.upper()


def _text_constants(text: str) -> dict[str, str]:
    constants: dict[str, str] = {}
    assign = re.compile(r"\b(?:const|let|var|final|static|String|string|val|var)?\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?\s*:?=\s*([`'\"])(.*?)\2")
    for line in text.splitlines():
        match = assign.search(line)
        if match:
            constants[match.group(1)] = match.group(3)
    return constants


def _resolve_text_fragments(line: str, constants: dict[str, str]) -> set[str]:
    values = set(re.findall(r"[`'\"]([^`'\"]+)[`'\"]", line))
    for name, value in constants.items():
        if re.search(rf"\b{re.escape(name)}\b", line):
            values.add(value)
    for match in re.finditer(r"([`'\"])([^`'\"]*)\1\s*\+\s*([A-Za-z_][A-Za-z0-9_]*|[`'\"]([^`'\"]*)[`'\"])", line):
        right = match.group(4) if match.group(4) is not None else constants.get(match.group(3), "")
        values.add(match.group(2) + right)
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*\+\s*([`'\"])([^`'\"]*)\2", line):
        if match.group(1) in constants:
            values.add(constants[match.group(1)] + match.group(3))
    for match in re.finditer(r"`([^`]*)`", line):
        template = match.group(1)
        resolved = template
        for var_name, value in constants.items():
            resolved = re.sub(r"\$\{\s*" + re.escape(var_name) + r"\s*\}", value, resolved)
        if "${" not in resolved:
            values.add(resolved)
    return {value for value in values if value}


def _line_looks_like_span(lower: str) -> bool:
    return "span" in lower or "tracer" in lower or "startactivity" in lower


def _line_looks_like_metric(lower: str) -> bool:
    return any(word in lower for word in ("counter", "histogram", "gauge", "meter", "metric", ".add(", ".record("))


def _line_looks_like_log(lower: str) -> bool:
    return bool(LOG_CALL.search(lower)) or ".log" in lower or ".error" in lower or ".warn" in lower or "log::" in lower


def _attributes_from_text(line: str) -> set[str]:
    attrs = set(re.findall(r"[`'\"]([A-Za-z_][A-Za-z0-9_.-]*)[`'\"]\s*[:=]", line))
    attrs.update(re.findall(r"\b([A-Za-z_][A-Za-z0-9_.-]*)\s*[:=]\s*[A-Za-z_][A-Za-z0-9_]*", line))
    return attrs


def _extract_named_field(line: str, field: str) -> str | None:
    match = re.search(rf"[`'\"]{re.escape(field)}[`'\"]\s*[:=]\s*[`'\"]([^`'\"]+)[`'\"]", line)
    return match.group(1) if match else None


def _redact_line(line: str) -> str:
    line = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1<redacted>", line)
    line = re.sub(r"(?i)((?:password|passwd|pwd|token|secret|authorization|cookie)\s*[:=]\s*)['\"]?[^,'\")\s]+", r"\1<redacted>", line)
    return line[:240]


def _collect_files(paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(child for child in path.rglob("*") if child.suffix in SOURCE_SUFFIXES and child.is_file()))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"source path does not exist: {path}")
    return files
