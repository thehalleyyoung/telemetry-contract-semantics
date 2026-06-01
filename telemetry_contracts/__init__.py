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
from .high_impact_filter import feature_scorecard, score_addition
from .project_semantics import infer_execution_semantics
from .repo_scan import scan_directory, scan_repo
from .service_report import generate_service_owner_report
from .static_checker import check_sources
from .validator import validate_events
from .bug_classes import BUG_CLASSES, HEADLINE_QUESTION, soundness_rows
from .mining import aggregate, mine_corpus, render_study_markdown, subject_record
from .formal_model import (
    discharge_formal_model,
    render_formal_model_markdown,
    render_traceability_markdown,
)
from .evaluation import (
    compare_baselines,
    load_gold_set,
    render_baselines_markdown,
    render_evaluation_markdown,
    score_gold_set,
)

__all__ = [
    "__version__",
    "analyze_events",
    "aggregate",
    "baseline",
    "BUG_CLASSES",
    "characterize_repo",
    "check_sources",
    "compare_baselines",
    "diagnose",
    "differential",
    "discharge_formal_model",
    "feature_scorecard",
    "generate_code_proposals",
    "generate_incident_readiness_report",
    "generate_service_owner_report",
    "HEADLINE_QUESTION",
    "import_otlp",
    "infer_contract",
    "infer_execution_semantics",
    "infer_temporal_order",
    "instrumentation_plan",
    "load_contract",
    "load_events_auto",
    "load_gold_set",
    "load_jsonl",
    "mine_corpus",
    "normalize_events",
    "render_baselines_markdown",
    "render_evaluation_markdown",
    "render_formal_model_markdown",
    "render_study_markdown",
    "render_traceability_markdown",
    "run_compiled_monitor",
    "run_benchmark",
    "run_pipeline",
    "scan_directory",
    "scan_repo",
    "score_addition",
    "score_gold_set",
    "semantic_differential",
    "soundness_rows",
    "subject_record",
    "validate_events",
    "write_pipeline_artifacts",
]
