from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ContractLoadError(ValueError):
    """Raised when a contract cannot be loaded or parsed."""


def load_contract(path: str | Path) -> dict[str, Any]:
    contract_path = Path(path)
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
