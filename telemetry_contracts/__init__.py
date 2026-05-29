"""Telemetry Contracts: validate observability as a correctness property."""

__version__ = "0.1.0"

from .benchmark import run_benchmark
from .incident_report import generate_incident_readiness_report
from .loader import load_contract, load_jsonl
from .monitor import run_compiled_monitor
from .otlp import load_otlp_json_detailed as import_otlp
from .service_report import generate_service_owner_report
from .static_checker import check_sources
from .validator import validate_events

__all__ = [
    "__version__",
    "check_sources",
    "generate_incident_readiness_report",
    "generate_service_owner_report",
    "import_otlp",
    "load_contract",
    "load_jsonl",
    "run_compiled_monitor",
    "run_benchmark",
    "validate_events",
]
