from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

CLAIMS: list[dict[str, Any]] = [
    {
        "id": "zero-config-existing-data",
        "claim": "The tool runs against telemetry you already have (arbitrary JSON/JSONL logs, a JSON array, native JSONL, or OTLP) with no contract authored first: `analyze` reports privacy/diagnosability findings and `infer-contract` writes a conservative draft contract.",
        "public_artifacts": ["README.md", "telemetry_contracts/adapters.py", "telemetry_contracts/discover.py", "telemetry_contracts/infer.py"],
        "tests": ["tests/test_adapters.py", "tests/test_discover.py", "tests/test_infer.py", "tests/test_cli_byod.py"],
        "fixtures": ["tests/fixtures/byod/app_logs.jsonl"],
        "benchmark_rows": [],
        "limitations": ["Kind inference and alias mapping are heuristic; low-confidence rows skip kind-specific checks and inferred contracts are drafts for review."],
    },
    {
        "id": "benchmark-public-fixtures",
        "claim": "The built-in benchmark ties public/reconstructed fixtures to expected semantic labels and precision/recall/F1 metrics.",
        "public_artifacts": ["README.md", "benchmarks/builtin.json", "reports/current_impact.json", "reports/current_impact.md"],
        "tests": ["tests/test_benchmark.py::test_builtin_benchmark_reports_labeled_historical_case"],
        "fixtures": ["case_studies/gitlab_2017_database_outage/reconstructed_events.jsonl", "case_studies/current/owasp_securetea_signin/Signin.js", "examples/benchmarks/privacy_static.events.jsonl"],
        "benchmark_rows": ["gitlab-2017-database-outage-reconstructed", "owasp-securetea-signin-current-static-and-hyperproperty", "benchmark-privacy-static-source"],
        "limitations": ["Finite checked-in fixtures only; not population-level recall."],
    },
    {
        "id": "ci-regression-gate",
        "claim": "CI can fail on new high-severity findings while allowing audited, owned, expiring baseline entries.",
        "public_artifacts": ["examples/ci/baseline.example.json", "examples/ci/github-actions.yml", "examples/ci/generic-ci.sh"],
        "tests": ["tests/test_ci_gate.py"],
        "fixtures": ["examples/ci/static_findings.example.json"],
        "benchmark_rows": ["benchmark-privacy-static-source"],
        "limitations": ["Baseline entries are exact finding keys; broad suppressions are intentionally unsupported."],
    },
    {
        "id": "sarif-static-runtime",
        "claim": "Static and runtime findings can be exported as SARIF with taxonomy-backed rule metadata for code scanning consumers.",
        "public_artifacts": ["telemetry_contracts/sarif.py", "docs/finding_taxonomy.json", "reports/current_impact.sarif"],
        "tests": ["tests/test_sarif.py", "tests/test_cli.py"],
        "fixtures": ["examples/ci/static_findings.example.json"],
        "benchmark_rows": ["benchmark-privacy-static-source", "benchmark-missing-correlation"],
        "limitations": ["SARIF locations are precise for source-span findings and best-effort for event-index findings."],
    },
    {
        "id": "deterministic-regeneration",
        "claim": "Current impact reports, benchmark Markdown, taxonomy summaries, paper tables, and this matrix are regenerated from checked-in artifacts.",
        "public_artifacts": ["reports/current_impact.json", "reports/current_impact.md", "reports/paper_tables.md", "docs/claims_evidence_matrix.json"],
        "tests": ["tests/test_regenerate.py"],
        "fixtures": ["benchmarks/builtin.json"],
        "benchmark_rows": ["all built-in benchmark rows"],
        "limitations": ["Runtime duration fields vary by machine; labels and finding codes are deterministic."],
    },
    {
        "id": "staged-pipeline-existing-repos",
        "claim": "A staged loop runs on a repository you did not instrument: it characterizes existing telemetry, diagnoses incident-readiness, plans high-impact additive instrumentation, synthesizes the missing signals offline, and re-analyzes differentially across rounds. Each round is safety-gated (a round that introduces a finding or drops the score is quarantined and rolled back), every stage is persisted as a SHA-keyed, provenance-carrying artifact, and generated code is emitted only as validated standalone proposals (parsed, compiled, and confirmed by the static checker) — never applied to the repo and never build/test-run.",
        "public_artifacts": ["telemetry_contracts/pipeline.py", "telemetry_contracts/artifacts.py", "telemetry_contracts/code_proposals.py", "telemetry_contracts/sarif.py", "docs/staged_pipeline.md"],
        "tests": ["tests/test_pipeline.py", "tests/test_pipeline_artifacts.py"],
        "fixtures": [],
        "benchmark_rows": [],
        "limitations": [
            "The applied instrumentation is an offline, deterministic synthesis stand-in; code proposals are standalone helper sketches that are not applied to the repository and whose target build/tests are not run.",
            "The loop runs on the dominant service for a single narrative; per-service breakdowns come from `scan --deep`.",
        ],
    },
    {
        "id": "high-impact-filter-and-reviewable-patches",
        "claim": "Every proposed instrumentation change is scored by a written high-impact rubric (analytic signal gained / added surface area, derived mechanically from unblocked questions and statically-confirmed signal names) and ships with a reviewable companion patch generated against the exact cloned commit and verified with `git apply --check`. Analysis deepens progressively across rounds (correlation -> ordering -> temporal -> privacy) only as the data actually gets richer, and a post-hoc scorecard re-scores the applied changes (predicted vs realized impact per surface area) as tool-maintenance metadata that is never a repository finding. Proven on real GitHub, GitLab, and Bitbucket repositories authored without this tool.",
        "public_artifacts": ["telemetry_contracts/high_impact_filter.py", "telemetry_contracts/code_proposals.py", "telemetry_contracts/pipeline.py", "docs/high_impact_filter.md"],
        "tests": ["tests/test_proposals_and_depth.py", "tests/test_real_repos.py"],
        "fixtures": [],
        "benchmark_rows": [],
        "limitations": [
            "The rubric is a deterministic decision aid, not an automatic gate; a tiny change can score high and necessary scaffolding can score low, so the breakdown is always reported.",
            "Companion patches add a brand-new file (a reviewable proposal); they are not integrated into existing call sites and are never applied. Re-running or replaying the target repo's build/tests remains out of scope without a sandbox.",
        ],
    },
    {
        "id": "corpus-mining-study",
        "claim": "A frozen, pinned-commit corpus of pre-existing repositories (addressed by exact 40-character commit SHA across GitHub, GitLab, and Bitbucket) is scanned and reduced to a single byte-deterministic dataset: a headline statistic (the share of telemetry-bearing repositories that cannot answer 'why did this request fail?'), per-bug-class prevalence with per-host breakdowns, and the diagnosability-score distribution. Each bug class has a precise, testable definition and an explicit soundness/incompleteness statement, and the headline uses the conservative finding-based correlation check so it never over-reports relative to the per-class prevalence.",
        "public_artifacts": ["telemetry_contracts/bug_classes.py", "telemetry_contracts/mining/__init__.py", "telemetry_contracts/mining/corpus.py", "telemetry_contracts/mining/study.py", "docs/evaluation/corpus_study.md"],
        "tests": ["tests/test_mining_study.py", "tests/test_corpus_mining_real.py"],
        "fixtures": ["benchmarks/corpus/tier1.json"],
        "benchmark_rows": [],
        "limitations": [
            "The corpus is a curated sample; prevalence figures describe the sampled repositories, not all software, and detection inherits each bug class's stated incompleteness.",
            "Only derived metrics and findings are retained (never copied source); per-subject licenses are recorded in the manifest.",
        ],
    },
    {
        "id": "ground-truth-precision-recall",
        "claim": "A hand-labeled curated conformance set (one objectively-checkable (sample, bug-class) pair per line, balanced positive/negative and covering every bug class) is scored against the shipped detectors to produce byte-deterministic per-class and overall precision, recall, and F1, a confusion matrix, a representative error analysis, and a Cohen's-kappa inter-rater slot. Labels are semantic ground truth (distinct from the operational detector's field set); every residual error on the curated set is a documented incompleteness or false-positive source. The metrics describe this curated set rather than a prevalence-representative sample, and the predictor's wiring is separately validated to agree exactly with an independent field oracle on telemetry harvested from real repositories.",
        "public_artifacts": ["telemetry_contracts/evaluation/__init__.py", "telemetry_contracts/evaluation/ground_truth.py", "telemetry_contracts/evaluation/scorer.py", "docs/evaluation/ground_truth.md"],
        "tests": ["tests/test_ground_truth_eval.py", "tests/test_ground_truth_real.py"],
        "fixtures": ["benchmarks/ground_truth/curated.jsonl"],
        "benchmark_rows": [],
        "limitations": [
            "Accuracy is measured on a curated gold set whose labels are objective but whose distribution is not a random sample of all telemetry; the headline F1 describes this set.",
            "The field-decidable classes are validated against an independent oracle on real events; the pattern-based classes (sensitive values, cardinality) inherit their stated precision-over-recall tuning.",
        ],
    },
    {
        "id": "baseline-comparison",
        "claim": "The shipped detectors are compared head-to-head, through the identical gold-set pipeline, against deterministic capability baselines: a deliberately naive field-name keyword detector (rule-light), an OpenTelemetry semantic-convention conformance checker (coverage-limited, with out-of-scope classes reported as coverage gaps rather than accuracy failures), and an offline LLM-baseline harness (prompt + parser + replay cache) whose shipped cache is a transparent hand-written surrogate policy that is explicitly NOT an LLM result. The comparison reports all-class and covered-class micro/macro precision/recall/F1, a symmetric per-item win/loss analysis, and an exact two-sided paired McNemar test; on the curated set the tool significantly outperforms every baseline. Baseline definitions are frozen before snapshotting, no threshold is tuned on the gold set, and every method sees only (events, bug_class).",
        "public_artifacts": ["telemetry_contracts/evaluation/baselines.py", "docs/evaluation/baselines.md"],
        "tests": ["tests/test_baselines.py", "tests/test_baselines_real.py"],
        "fixtures": ["benchmarks/ground_truth/curated.jsonl", "benchmarks/baselines/llm_recorded.json"],
        "benchmark_rows": [],
        "limitations": [
            "The baselines are deliberately scoped capability comparators, not state-of-the-art detectors; the head-to-head numbers describe the curated conformance set, not a prevalence-representative sample.",
            "The LLM-baseline row replays a transparent deterministic surrogate, not a commercial model; it demonstrates the offline harness and a different error profile and makes no claim about real LLM accuracy.",
        ],
    },
    {
        "id": "formal-model",
        "claim": "The core semantic guarantees are stated precisely, tied mechanically to the code that implements them and the test that witnesses them, and discharged by deterministic executable checks rather than asserted in prose. Thirteen obligations across six families are checked: contract-refinement order axioms (reflexivity, transitivity, antisymmetry, and order-soundness in the under-instrumentation direction), monotonicity of the staged improvement loop (non-decreasing diagnosability with no applied regressions, and quarantine of regressing rounds), termination (bounded rounds and monotonic gap exclusion so no gap is re-planned), assume-guarantee discharge (a satisfying trace passes, a violating trace flags), attribute-presence abstract-domain soundness (a field present in an event is never reported absent), and transformation preservation (a benign transform preserves obligations while a destructive one that drops a required correlation field is detected). The tool emits a machine-checkable verdict per obligation, so the paper cites a checked count.",
        "public_artifacts": ["telemetry_contracts/formal_model.py", "docs/formal_model.md"],
        "tests": ["tests/test_formal_model.py", "tests/test_formal_model_real.py"],
        "fixtures": [],
        "benchmark_rows": [],
        "limitations": [
            "The witnesses discharge the guarantees over built-in finite fixtures (plus real harvested events for the data-dependent abstract-domain and refinement witnesses); they are executable conformance checks, not mechanized proofs in a theorem prover.",
            "The approximation direction of each guarantee (exact, over-, or under-approximation) is documented and tested, but the soundness argument for the approximation itself is given in prose in docs/formal_model.md.",
        ],
    },
    {
        "id": "execution-proof",
        "claim": "The tool produces runtime evidence that its own deterministically generated instrumentation proposals work: it regenerates each snippet from trusted (gap, library_kind) fields (never the proposal's stored text), validates intended field names, checks the snippet against a strict exact-shape AST allowlist, and runs the validated snippet in a hardened, isolated subprocess (python -I -S -B -E, stripped environment, fresh empty cwd, stdin to /dev/null, close_fds, timeout, and POSIX CPU/file-size rlimits). For the stdlib logging variant it captures the emitted records via a private non-propagating logger and proves the promised field names are emitted (status emission-clean); the OpenTelemetry variant degrades honestly to needs-optional-dep when the SDK is absent. The tool never executes the target repository's code and never runs its build/test; executed events are labeled evidence only and are never folded into scoring or the differential, so the deterministic scores are unaffected.",
        "public_artifacts": ["telemetry_contracts/execution.py", "docs/execution_proof.md"],
        "tests": ["tests/test_execution.py", "tests/test_execution_real.py"],
        "fixtures": [],
        "benchmark_rows": [],
        "limitations": [
            "This is an isolated generated-instrumentation compile/load/emission proof, not the target repository's build or test suite, which is intentionally never run in a shared environment.",
            "Under isolated python (-S) a site-installed OpenTelemetry SDK is intentionally invisible, so the OTel variant reports needs-optional-dep rather than proving span emission in this environment.",
        ],
    },
    {
        "id": "github-action-ci",
        "claim": "A composite GitHub Action wraps the scan/diagnose engines so any repository can add observability scanning to its PR checks in three lines of YAML. The Action produces a deterministic CI report (diagnosability score, severity counts, top under-instrumentation gaps, unanswered incident questions), evaluates a configurable pass/fail gate (a score floor plus a finding-severity threshold), uploads findings to the Security tab as SARIF via GitHub code scanning, and posts a concise PR comment that can show a score delta versus the base branch. The underlying ci-report command is byte-deterministic: the same inputs always yield the same report JSON, the same PR-comment bytes, and the same SARIF, with no wall-clock or RNG. The repository dogfoods the Action against its own example telemetry on every push.",
        "public_artifacts": ["telemetry_contracts/github_action.py", "action.yml", "docs/github_action.md", ".github/workflows/observability-self-test.yml"],
        "tests": ["tests/test_github_action.py", "tests/test_github_action_real.py"],
        "fixtures": [],
        "benchmark_rows": [],
        "limitations": [
            "The base-branch score delta requires the workflow to compute a base report (e.g. via a second checkout); the Action does not check out the base branch on its own.",
            "SARIF upload and PR commenting depend on the caller granting security-events: write and pull-requests: write permissions respectively; both integrations can be disabled via inputs.",
        ],
    },
    {
        "id": "scorecard-badge",
        "claim": "The tool renders a shareable observability score badge and scorecard directly from a scan, so a repository can display its diagnosability score the same way it displays build status or coverage. From any directory (or a prior CI report) it emits a shields-style flat badge SVG, a live shields.io endpoint JSON, or a richer scorecard card listing the score, verdict, and top under-instrumentation gaps. All three renderings are byte-deterministic: the same inputs always produce identical bytes, the SVG is well-formed XML, XML special characters are escaped, and the color band is a pure function of the score (grey when no telemetry is discovered). The repository dogfoods its own badge in the README.",
        "public_artifacts": ["telemetry_contracts/scorecard.py", "docs/scorecard_badge.md"],
        "tests": ["tests/test_scorecard.py", "tests/test_scorecard_real.py"],
        "fixtures": [],
        "benchmark_rows": [],
        "limitations": [
            "The badge reports the diagnosability score only; the scorecard summarizes the top gaps but is not a substitute for the full findings report.",
            "Publishing a live shields.io endpoint requires the caller to host the endpoint JSON (e.g. as a raw repository file); the tool only renders it.",
        ],
    },
    {
        "id": "browser-playground",
        "claim": "A static, dependency-free browser playground runs the pure-stdlib engine entirely client-side under Pyodide (no backend, nothing uploaded), so a newcomer can paste the telemetry they already have and instantly see their diagnosability score and under-instrumentation gaps. It auto-detects JSON lines, a JSON array, logfmt, or an OTLP JSON export; ships one-click example datasets drawn from existing repository fixtures; and encodes the input into the URL so results are shareable without a server. The browser calls a single shared, tested entrypoint (analyze_text) that is byte-deterministic and matches the CLI. A CI smoke test loads the engine under Pyodide and asserts it imports and analyzes a known sample deterministically, and the committed bundle is byte-reproducible from a build script.",
        "public_artifacts": ["telemetry_contracts/playground.py", "playground/build.py", "playground/index.html", "playground/app.js", "playground/smoke_test.mjs", "docs/playground.md", ".github/workflows/playground-smoke.yml"],
        "tests": ["tests/test_playground.py", "tests/test_playground_real.py"],
        "fixtures": [],
        "benchmark_rows": [],
        "limitations": [
            "The playground analyzes pasted/loaded telemetry text only; the deeper repository scan, semantics inference, and staged pipeline run via the CLI, not in the browser.",
            "The Pyodide runtime and the engine bundle are loaded at page open, so the first analysis incurs a one-time load cost; subsequent analyses are instant.",
        ],
    },
    {
        "id": "launch-assets",
        "claim": "The repository ships byte-deterministic launch and demo assets generated from real data: a self-contained terminal SVG and an asciicast of a real scan-repo run against a public repository authored without this tool, and a 1200x630 social/OpenGraph card built from the frozen corpus headline statistic. A launch blog post and Show-HN narrative present the corpus result with an exact, reproducible command, and a CONTRIBUTING guide frames good-first-issues around adding corpus subjects and gold labels. The rendering helpers are pure functions (fixed geometry, fixed asciicast timing, XML-escaped, no wall-clock or RNG); the committed assets are reproducible from docs/launch/build.py and a test fails if they drift.",
        "public_artifacts": ["telemetry_contracts/launch.py", "docs/launch/build.py", "docs/launch/blog_post.md", "docs/launch/show_hn.md", "docs/launch/demo.svg", "docs/launch/social_card.svg", "CONTRIBUTING.md"],
        "tests": ["tests/test_launch.py"],
        "fixtures": [],
        "benchmark_rows": [],
        "limitations": [
            "The demo transcript is real captured output committed as text; reproducing it live requires network access to clone the subject repository.",
            "The social card and blog headline summarize a small, demonstrative frozen corpus; the numbers are honest for that corpus and scale with additional corpus subjects.",
        ],
    },
]


def claims_evidence_matrix(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    commit = _git_commit(root)
    rows = []
    for item in CLAIMS:
        row = dict(item)
        row["commit"] = commit
        row["evidence_exists"] = {path: (root / path).exists() for path in item["public_artifacts"] + item["fixtures"] if path != "all built-in benchmark rows"}
        rows.append(row)
    return {"schema_version": "1.0", "claims": rows, "summary": {"claims": len(rows), "commit": commit}}


def write_claims_evidence_matrix(path: str | Path, repo_root: str | Path = ".") -> dict[str, Any]:
    report = claims_evidence_matrix(repo_root)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"
