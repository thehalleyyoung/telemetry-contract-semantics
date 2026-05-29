from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class Finding:
    severity: Severity
    code: str
    message: str
    path: str
    contract_path: str | None = None
    event_index: int | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "error": 2}


def has_at_least(findings: list[Finding], severity: str) -> bool:
    threshold = SEVERITY_ORDER[severity]
    return any(SEVERITY_ORDER[item.severity] >= threshold for item in findings)
