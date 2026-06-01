"""Telemetry Contracts: validate observability as a correctness property."""

__version__ = "0.1.0"

from .adapters import load_events_auto, normalize_events
from .benchmark import run_benchmark
from .discover import analyze_events
from .incident_report import generate_incident_readiness_report
from .infer import infer_contract, infer_temporal_order
from .loader import load_contract, load_jsonl
from .monitor import run_compiled_monitor
from .otlp import load_otlp_json_detailed as import_otlp
from .pipeline import (
    baseline,
    characterize_repo,
    diagnose,
    differential,
    instrumentation_plan,
    run_pipeline,
    semantic_differential,
)
from .artifacts import write_pipeline_artifacts
from .code_proposals import generate_code_proposals
from .project_semantics import infer_execution_semantics
from .repo_scan import scan_directory, scan_repo
from .service_report import generate_service_owner_report
from .static_checker import check_sources
from .validator import validate_events

__all__ = [
    "__version__",
    "analyze_events",
    "baseline",
    "characterize_repo",
    "check_sources",
    "diagnose",
    "differential",
    "generate_code_proposals",
    "generate_incident_readiness_report",
    "generate_service_owner_report",
    "import_otlp",
    "infer_contract",
    "infer_execution_semantics",
    "infer_temporal_order",
    "instrumentation_plan",
    "load_contract",
    "load_events_auto",
    "load_jsonl",
    "normalize_events",
    "run_compiled_monitor",
    "run_benchmark",
    "run_pipeline",
    "scan_directory",
    "scan_repo",
    "semantic_differential",
    "validate_events",
    "write_pipeline_artifacts",
]
