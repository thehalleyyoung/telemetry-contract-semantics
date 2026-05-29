from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


class ContractLoadError(ValueError):
    """Raised when a contract cannot be loaded or parsed."""


_SIGNAL_SECTIONS = {"spans", "metrics", "logs"}
_ID_LIST_SECTIONS = {"scenarios", "temporal_sequences", "temporal_properties", "alternative_obligations"}
_OBJECT_MERGE_SECTIONS = {"metadata", "privacy_classifications", "field_definitions", "static_expectations", "static_rules", "correlation", "assume_guarantee"}
_COMPOSITION_KEYS = ("extends", "inherits")


def load_contract(path: str | Path) -> dict[str, Any]:
    """Load a JSON/YAML contract and resolve any relative inheritance chain."""

    return load_contract_with_composition(path)["contract"]


def load_contract_with_composition(path: str | Path) -> dict[str, Any]:
    """Load a contract and return the resolved contract plus composition evidence.

    Contracts may declare top-level ``extends`` or ``inherits`` as a string or list of
    strings. Parent paths are resolved relative to the child contract. Parent
    obligations are merged first; child declarations may strengthen or add
    obligations. Separate composition reports use the refinement checker to catch
    weakening overrides.
    """

    root = Path(path)
    contract, evidence = _resolve_contract(root, [])
    return {"contract": contract, "composition": evidence}


def load_contract_raw(path: str | Path) -> dict[str, Any]:
    """Load a contract file without resolving inheritance."""

    return _load_contract_raw(Path(path))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    jsonl_path = Path(path)
    if not jsonl_path.exists():
        raise ContractLoadError(f"telemetry file does not exist: {jsonl_path}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractLoadError(f"invalid JSONL at {jsonl_path}:{line_number}: {exc}") from exc
        if not isinstance(event, dict):
            raise ContractLoadError(f"JSONL event at {jsonl_path}:{line_number} must be an object")
        event.setdefault("_line", line_number)
        events.append(event)
    return events


def compose_contracts(parents: list[dict[str, Any]], child: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic inherited contract denotation for parent(s)+child."""

    merged: dict[str, Any] = {}
    for parent in parents:
        merged = _merge_contract_dicts(merged, _strip_composition_keys(parent))
    merged = _merge_contract_dicts(merged, _strip_composition_keys(child))
    return merged


def composition_parents(contract: dict[str, Any]) -> list[str]:
    raw: Any = None
    for key in _COMPOSITION_KEYS:
        if key in contract:
            raw = contract[key]
            break
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list) and all(isinstance(item, str) and item for item in raw):
        return list(raw)
    raise ContractLoadError("contract extends/inherits must be a string or non-empty list of strings")


def _resolve_contract(path: Path, stack: list[Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    contract_path = path.resolve()
    if contract_path in stack:
        chain = " -> ".join(str(item) for item in [*stack, contract_path])
        raise ContractLoadError(f"contract inheritance cycle detected: {chain}")
    raw = _load_contract_raw(contract_path)
    parent_refs = composition_parents(raw)
    resolved_parents: list[dict[str, Any]] = []
    parent_entries: list[dict[str, Any]] = []
    for ref in parent_refs:
        parent_path = (contract_path.parent / ref).resolve()
        parent_contract, parent_evidence = _resolve_contract(parent_path, [*stack, contract_path])
        resolved_parents.append(parent_contract)
        parent_entries.append(
            {
                "path": str(parent_path),
                "service": parent_contract.get("service", ""),
                "parents": parent_evidence.get("parents", []),
                "inherited_signal_keys": _signal_keys(parent_contract),
            }
        )
    resolved = compose_contracts(resolved_parents, raw) if resolved_parents else _strip_composition_keys(raw)
    evidence = {
        "path": str(contract_path),
        "parents": parent_entries,
        "has_composition": bool(parent_entries),
        "inherited_signal_keys": sorted({key for parent in resolved_parents for key in _signal_keys(parent)}),
        "declared_signal_keys": _signal_keys(raw),
        "resolved_signal_keys": _signal_keys(resolved),
        "overridden_signal_keys": sorted(set(_signal_keys(raw)) & {key for parent in resolved_parents for key in _signal_keys(parent)}),
    }
    return resolved, evidence


def _load_contract_raw(contract_path: Path) -> dict[str, Any]:
    if not contract_path.exists():
        raise ContractLoadError(f"contract file does not exist: {contract_path}")
    text = contract_path.read_text(encoding="utf-8")
    suffix = contract_path.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ContractLoadError(f"invalid JSON in {contract_path}: {exc}") from exc
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise ContractLoadError(
                f"YAML contract {contract_path} requires PyYAML; use JSON or install telemetry-contracts[yaml]"
            ) from exc
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:  # type: ignore[attr-defined]
            raise ContractLoadError(f"invalid YAML in {contract_path}: {exc}") from exc
    else:
        raise ContractLoadError(f"unsupported contract extension for {contract_path}; use .json, .yaml, or .yml")
    if not isinstance(data, dict):
        raise ContractLoadError(f"contract root must be an object: {contract_path}")
    return data


def _strip_composition_keys(contract: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(contract)
    for key in _COMPOSITION_KEYS:
        result.pop(key, None)
    return result


def _merge_contract_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in _SIGNAL_SECTIONS and isinstance(value, list):
            result[key] = _merge_named_lists(result.get(key, []), value, key_name="name")
        elif key in _ID_LIST_SECTIONS and isinstance(value, list):
            result[key] = _merge_named_lists(result.get(key, []), value, key_name="id")
        elif key in _OBJECT_MERGE_SECTIONS and isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dicts(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge_dicts(result[key], value)
        elif isinstance(result.get(key), list) and isinstance(value, list):
            result[key] = _merge_named_lists(result[key], value, key_name="id")
        else:
            result[key] = copy.deepcopy(value)
    return result


def _merge_named_lists(base: Any, override: list[Any], key_name: str) -> list[Any]:
    if not isinstance(base, list):
        base = []
    result = copy.deepcopy(base)
    index_by_key = {item.get(key_name): index for index, item in enumerate(result) if isinstance(item, dict) and item.get(key_name)}
    for item in override:
        if isinstance(item, dict) and item.get(key_name) in index_by_key:
            result[index_by_key[item[key_name]]] = _deep_merge_dicts(result[index_by_key[item[key_name]]], item)
        elif item in result:
            continue
        else:
            result.append(copy.deepcopy(item))
    return result


def _signal_keys(contract: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for section in sorted(_SIGNAL_SECTIONS):
        for spec in contract.get(section, []) or []:
            if isinstance(spec, dict) and spec.get("name"):
                keys.append(f"{section[:-1]}:{spec['name']}")
    return sorted(keys)
