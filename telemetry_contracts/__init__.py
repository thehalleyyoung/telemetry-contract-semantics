"""Telemetry Contracts: validate observability as a correctness property."""

__version__ = "0.1.0"

from .adapters import load_events_auto, normalize_events
from .benchmark import run_benchmark
from .discover import analyze_events
from .incident_report import generate_incident_readiness_report
from .infer import infer_contract
from .loader import load_contract, load_jsonl
from .monitor import run_compiled_monitor
from .otlp import load_otlp_json_detailed as import_otlp
from .repo_scan import scan_directory, scan_repo
from .service_report import generate_service_owner_report
from .static_checker import check_sources
from .validator import validate_events

__all__ = [
    "__version__",
    "analyze_events",
    "check_sources",
    "generate_incident_readiness_report",
    "generate_service_owner_report",
    "import_otlp",
    "infer_contract",
    "load_contract",
    "load_events_auto",
    "load_jsonl",
    "normalize_events",
    "run_compiled_monitor",
    "run_benchmark",
    "scan_directory",
    "scan_repo",
    "validate_events",
]
