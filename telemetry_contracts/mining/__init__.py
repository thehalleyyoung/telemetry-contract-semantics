"""Corpus-scale mining study over pre-existing repositories.

This package turns the deterministic per-repository engine (``scan-repo``) into a
reproducible *study*: a frozen, pinned-commit subject corpus is scanned and
reduced to a single deterministic dataset and human-readable report. The headline
statistic — *what fraction of real repositories cannot answer "why did this
request fail?"* — is computed here, byte-reproducibly, so it can be cited
identically in documentation and in any future paper.

Public surface:

* :func:`load_corpus_manifest` / :class:`CorpusManifestError` — declarative,
  pinned-SHA subject lists.
* :func:`subject_record` — reduce one scan result to a flat study row.
* :func:`aggregate` — combine subject rows into prevalence, score distribution,
  and the headline statistic.
* :func:`render_study_markdown` — a deterministic report.
* :func:`mine_corpus` — clone+scan every manifest subject (network).
"""

from __future__ import annotations

from .corpus import (
    CorpusManifestError,
    CorpusSubject,
    load_corpus_manifest,
    parse_corpus_manifest,
)
from .cache import ResultCache, engine_fingerprint, options_fingerprint
from .characteristics import detect_characteristics
from .correlate import correlate, render_correlation_markdown
from .plots import render_plots
from .runner import (
    StatusTable,
    download_corpus,
    download_subject,
    run_corpus,
    subject_checkout_dir,
)
from .study import (
    aggregate,
    analyze_checkout,
    mine_corpus,
    record_facts,
    record_from_facts,
    render_study_markdown,
    subject_record,
)

__all__ = [
    "CorpusManifestError",
    "CorpusSubject",
    "load_corpus_manifest",
    "parse_corpus_manifest",
    "ResultCache",
    "engine_fingerprint",
    "options_fingerprint",
    "detect_characteristics",
    "correlate",
    "render_correlation_markdown",
    "render_plots",
    "StatusTable",
    "download_corpus",
    "download_subject",
    "run_corpus",
    "subject_checkout_dir",
    "aggregate",
    "analyze_checkout",
    "mine_corpus",
    "record_facts",
    "record_from_facts",
    "render_study_markdown",
    "subject_record",
]
