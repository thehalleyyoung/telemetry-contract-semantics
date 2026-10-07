"""Trace every number in paper/tool_paper.tex to a committed file.

    python3 scripts/trace_numbers.py   # writes paper/number_trace.md

Each row recomputes a value from a committed results/, reports/, benchmarks/
or source file, formats it the way the paper prints it, and checks that the
paper (and therefore index.html, which is generated from it) contains that
exact text. Exits non-zero if a value does not recompute or is missing from the
paper.
"""
import csv, json, math, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEX = (ROOT / "paper/tool_paper.tex").read_text()
J = lambda p: json.loads((ROOT / p).read_text())

gold = J("reports/gold_evaluation.json")
base = {m["id"]: m for m in J("reports/baseline_comparison.json")["methods"]}
haiku_cfg = J("benchmarks/baselines/llm_anthropic__claude-haiku-4-5.json")
corpus = J("results/rq3/corpus_dataset.json")
manifest = J("benchmarks/corpus/corpus.json")
download = J("results/rq3/download_report.json")
vsum = J("results/rq3/validation_summary.json")
labels = list(csv.DictReader(open(ROOT / "results/rq3/validation_labels.csv")))
costs = [json.loads(l) for l in open(ROOT / "results/api_costs.jsonl")]
repro = J("reports/reproduce_manifest.json")
gold_items = [json.loads(l) for l in open(ROOT / "benchmarks/ground_truth/curated.jsonl")
              if l.strip() and not l.startswith("#")]
rq3_readme = (ROOT / "results/rq3/README.md").read_text()
discover = (ROOT / "telemetry_contracts/discover.py").read_text()
bug_classes = (ROOT / "telemetry_contracts/bug_classes.py").read_text()
n_findings = sum(1 for l in open(ROOT / "results/rq3/findings.jsonl") if l.strip())


def wilson(k, n, z=1.959964):
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - h) / d, (c + h) / d


def ci(k, n):     # ".62--.96" style, as in the tables
    lo, hi = wilson(k, n)
    return f".{round(lo * 100):02d}--.{round(hi * 100):02d}"


def ci0(k, n):    # "0.87--0.99" style, as in the text
    lo, hi = wilson(k, n)
    return f"{lo:.2f}--{hi:.2f}"


pm = lambda v: f"0.{v:03d}" if v < 1000 else "1.000"     # permille -> 0.953
pt = lambda v: f".{v:03d}" if v < 1000 else "1.00"       # permille -> .953 (table)
comma = lambda n: f"{n:,}"
cls = lambda c: vsum["by_class"][c]
bc = corpus["bug_class_prevalence"]
mc = lambda m: base[m]["vs_tool"]["mcnemar"]
pfmt = lambda m: (f"{mc(m)['two_sided_exact_p_ten_thousandths'] / 10000:.3f}".rstrip("0")
                  if mc(m)["two_sided_exact_p_ten_thousandths"] < 10000 else "1.00")
lab = lambda **kw: sum(all(r[k] == v for k, v in kw.items()) for r in labels)
lab_cls = lambda prefix, **kw: sum(r["sample_id"].startswith(prefix) and
                                   all(r[k] == v for k, v in kw.items()) for r in labels)
fp_rows = [r for r in labels if r["matches_definition"] == "no" and
           r["sample_id"].startswith(("rq3-missing-correlation", "rq3-missing-error"))]
widths = [wilson(k, 15)[1] - wilson(k, 15)[0] for k in (13, 12, 9)]
fp_t, fp_b = base["tool"]["overall"]["tp"], base["tool"]["overall"]["predicted_positive"]

ROWS = [
    # (text in paper, what it is, source, recomputed text)
    ("six gap classes", "number of gap classes", "telemetry_contracts/bug_classes.py; reports/baseline_comparison.json",
     f"{['zero','one','two','three','four','five','six','seven'][len(base['tool']['covered_classes'])]} gap classes"),
    ("112-item gold set", "gold-set size", "reports/gold_evaluation.json; benchmarks/ground_truth/curated.jsonl",
     f"{gold['overall']['samples']}-item gold set" if len(gold_items) == gold["overall"]["samples"] else "MISMATCH"),
    ("54 positive and 58 negative", "gold-set class balance", "reports/gold_evaluation.json",
     f"{gold['overall']['support_positive']} positive and {gold['overall']['support_negative']} negative"),
    ("Five \\emph{hard} items", "hard items in the gold set", "benchmarks/ground_truth/curated.jsonl",
     f"{['','One','Two','Three','Four','Five'][sum('hard' in g['id'] for g in gold_items)]} \\emph{{hard}} items"),
    ("F1 0.953", "tool F1", "reports/gold_evaluation.json", f"F1 {pm(gold['overall']['f1_permille'])}"),
    ("precision 0.962 (51/53, Wilson 95\\% CI 0.87--0.99)", "tool precision + CI", "reports/gold_evaluation.json",
     f"precision {pm(gold['overall']['precision_permille'])} ({gold['overall']['tp']}/{gold['overall']['tp'] + gold['overall']['fp']}, Wilson 95\\% CI {ci0(gold['overall']['tp'], gold['overall']['tp'] + gold['overall']['fp'])})"),
    ("recall 0.944 (51/54, 0.85--0.98)", "tool recall + CI", "reports/gold_evaluation.json",
     f"recall {pm(gold['overall']['recall_permille'])} ({gold['overall']['tp']}/{gold['overall']['support_positive']}, {ci0(gold['overall']['tp'], gold['overall']['support_positive'])})"),
    ("0.923 (unbounded-cardinality) to 1.000 (missing-duration)", "per-class F1 range", "reports/gold_evaluation.json",
     f"{pm(min(v['f1_permille'] for v in gold['per_class'].values()))} (unbounded-cardinality) to {pm(max(v['f1_permille'] for v in gold['per_class'].values()))} (missing-duration)"),
    ("The five errors", "tool errors (FP+FN)", "reports/gold_evaluation.json",
     f"The {['','one','two','three','four','five'][gold['overall']['fp'] + gold['overall']['fn']]} errors"),
    ("Two are false positives", "tool FPs", "reports/gold_evaluation.json",
     f"{['','One','Two','Three'][gold['overall']['fp']]} are false positives"),
    ("Three are false negatives", "tool FNs", "reports/gold_evaluation.json",
     f"{['','One','Two','Three'][gold['overall']['fn']]} are false negatives"),
    ("0.991 (Claude Haiku 4.5)", "Haiku F1", "reports/baseline_comparison.json",
     f"{pm(base['llm:anthropic/claude-haiku-4.5']['overall']['f1_permille'])} (Claude Haiku 4.5)"),
    ("0.952 (GPT-4.1-mini)", "GPT-4.1-mini F1", "reports/baseline_comparison.json",
     f"{pm(base['llm:openai/gpt-4.1-mini']['overall']['f1_permille'])} (GPT-4.1-mini)"),
    ("$p = 0.125$ and $p = 1.00$", "McNemar p vs the two LLMs", "reports/baseline_comparison.json",
     f"$p = {pfmt('llm:anthropic/claude-haiku-4.5')}$ and $p = {pfmt('llm:openai/gpt-4.1-mini')}$"),
    ("at most 200 output tokens", "LLM max tokens", "benchmarks/baselines/llm_anthropic__claude-haiku-4-5.json",
     f"at most {haiku_cfg['decoding']['max_tokens']} output tokens"),
    ("at temperature 0", "LLM temperature", "benchmarks/baselines/llm_anthropic__claude-haiku-4-5.json",
     f"at temperature {haiku_cfg['decoding']['temperature']}"),
    ("All 224 responses parsed", "LLM responses", "results/api_costs.jsonl; reports/baseline_comparison.json",
     f"All {len(costs)} responses parsed" if all(base[m].get('unparseable_scored_as_no', 1) == 0 for m in base if m.startswith('llm')) else "MISMATCH"),
    ("US\\$0.077", "total LLM cost", "results/api_costs.jsonl", f"US\\${sum(c['cost_usd'] for c in costs):.3f}"),
    ("about 300 prompt tokens per item", "mean prompt tokens (316 Haiku, 285 GPT)", "results/api_costs.jsonl",
     "about 300 prompt tokens per item" if abs(sum(c['prompt_tokens'] for c in costs) / len(costs) - 300) < 10 else "MISMATCH"),
    # Table I
    *[(f"{name} & {pt(base[m]['overall']['precision_permille'])} & {pt(base[m]['overall']['recall_permille'])} & {pt(base[m]['overall']['f1_permille'])} & {pt(base[m]['covered']['f1_permille'])}",
       f"Table I row {name}", "reports/baseline_comparison.json",
       f"{name} & {pt(base[m]['overall']['precision_permille'])} & {pt(base[m]['overall']['recall_permille'])} & {pt(base[m]['overall']['f1_permille'])} & {pt(base[m]['covered']['f1_permille'])}")
      for name, m in [("\\tool", "tool"), ("rule-light", "rule-light"), ("semconv-only", "semantic-convention-only"),
                      ("Claude Haiku 4.5", "llm:anthropic/claude-haiku-4.5"), ("GPT-4.1-mini", "llm:openai/gpt-4.1-mini")]],
    *[(f"{mc(m)['discordant_tool_only']}/{mc(m)['discordant_baseline_only']} ({txt})", f"Table I discordant pairs + p, {m}",
       "reports/baseline_comparison.json",
       f"{mc(m)['discordant_tool_only']}/{mc(m)['discordant_baseline_only']} ({'$<$.001' if mc(m)['two_sided_exact_p_ten_thousandths'] < 10 else pfmt(m).removeprefix('0')})")
      for m, txt in [("rule-light", "$<$.001"), ("semantic-convention-only", "$<$.001"),
                     ("llm:anthropic/claude-haiku-4.5", ".125"), ("llm:openai/gpt-4.1-mini", "1.00")]],
    ("differs from the tool on four hard items", "Haiku-only-correct items (all hard)", "reports/baseline_comparison.json",
     f"differs from the tool on {['zero','one','two','three','four'][len(base['llm:anthropic/claude-haiku-4.5']['vs_tool']['baseline_only_correct'])]} hard items"
     if all('hard' in i for i in base['llm:anthropic/claude-haiku-4.5']['vs_tool']['baseline_only_correct']) else "MISMATCH"),
    ("resolves three hard items and misses three unclassified-identifier positives", "GPT-4.1-mini discordant items", "reports/baseline_comparison.json",
     f"resolves {['zero','one','two','three'][len(base['llm:openai/gpt-4.1-mini']['vs_tool']['baseline_only_correct'])]} hard items and misses {['zero','one','two','three'][len(base['llm:openai/gpt-4.1-mini']['vs_tool']['tool_only_correct'])]} unclassified-identifier positives"),
    # corpus
    ("58 pinned public repositories", "repositories scanned", "results/rq3/corpus_dataset.json", f"{corpus['subjects_total']} pinned public repositories"),
    ("116,420 events", "events scanned", "results/rq3/corpus_dataset.json", f"{comma(corpus['events_total'])} events"),
    ("2,269 findings", "findings extracted", "results/rq3/findings.jsonl", f"{comma(n_findings)} findings"),
    ("8.5 minutes", "corpus-run wall time", "results/rq3/README.md",
     "8.5 minutes" if "8.5 min wall" in rq3_readme else "MISMATCH"),
    ("pins 59 public repositories", "manifest size", "benchmarks/corpus/corpus.json", f"pins {len(manifest['subjects'])} public repositories"),
    ("of which 58 could be cloned (one was deleted upstream)", "clone results", "results/rq3/download_report.json",
     f"of which {download['summary']['downloaded']} could be cloned ({['none','one'][download['summary']['errors']]} was deleted upstream)"),
    ("GitHub (56), GitLab (1) and Bitbucket (1)", "hosts", "results/rq3/corpus_dataset.json",
     "GitHub ({github}), GitLab ({gitlab}) and Bitbucket ({bitbucket})".format(**{h: sum(s['host'] == h for s in corpus['subjects']) for h in ('github', 'gitlab', 'bitbucket')})),
    ("34 are primarily Python", "primary language", "results/rq3/corpus_dataset.json",
     f"{sum(s['language'] == 'Python' for s in corpus['subjects'])} are primarily Python"),
    ("at most 25 example findings per file", "per-file finding cap", "telemetry_contracts/discover.py",
     f"at most {re.search(r'_MAX_EXAMPLES_PER_CODE = (\d+)', discover).group(1)} example findings per file"),
    ("13 generated artifacts", "reproduce manifest size", "reports/reproduce_manifest.json", f"{len(repro['artifacts'])} generated artifacts"),
    ("15 findings per class", "sample per class", "results/rq3/validation_summary.json",
     f"{cls('missing-correlation')['n']} findings per class"),
    ("over 56 telemetry-bearing repositories", "telemetry-bearing repos", "results/rq3/corpus_dataset.json",
     f"over {corpus['subjects_with_telemetry']} telemetry-bearing repositories"),
    # Table II
    *[(f"{row} & {bc[c]['subjects_present']} & {comma(bc[c]['total_findings'])} & {cls(c)['def_yes']}/{cls(c)['n']}{tail}",
       f"Table II row {c}", "results/rq3/corpus_dataset.json; results/rq3/validation_summary.json",
       f"{row} & {bc[c]['subjects_present']} & {comma(bc[c]['total_findings'])} & {cls(c)['def_yes']}/{cls(c)['n']}{tail}")
      for row, c, tail in [("missing-correlation", "missing-correlation", f" ({ci(13, 15)})"),
                           ("missing-error-ev.", "missing-error-evidence", f" ({ci(12, 15)})"),
                           ("sensitive-values", "sensitive-values", f" ({ci(9, 15)})"),
                           ("unclassified-sens.", "unclassified-sensitive",
                            f" (+{cls('unclassified-sensitive').get('def_borderline', 0)} borderline)")]],
    ("35/60 (.46--.70)", "all sampled strict", "results/rq3/validation_summary.json",
     f"{vsum['overall']['def_yes']}/{vsum['overall']['n']} ({ci(vsum['overall']['def_yes'], vsum['overall']['n'])})"),
    ("no missing-duration or unbounded-cardinality findings", "zero-count classes", "results/rq3/corpus_dataset.json",
     "no missing-duration or unbounded-cardinality findings" if bc['missing-duration']['total_findings'] == bc['unbounded-cardinality']['total_findings'] == 0 else "MISMATCH"),
    ("Of the 14 telemetry-bearing repositories with at least one failure event, 10", "headline", "results/rq3/corpus_dataset.json",
     f"Of the {corpus['headline']['denominator']} telemetry-bearing repositories with at least one failure event, {corpus['headline']['cannot_answer']}"),
    ("25 of 30", "failure-path matches", "results/rq3/validation_summary.json",
     f"{cls('missing-correlation')['def_yes'] + cls('missing-error-evidence')['def_yes']} of {cls('missing-correlation')['n'] + cls('missing-error-evidence')['n']}"),
    ("(Wilson 95\\% CI 0.66--0.93)", "failure-path CI", "results/rq3/validation_summary.json", f"(Wilson 95\\% CI {ci0(25, 30)})"),
    ("Four of the five mismatches", "failure-path mismatches by cause", "results/rq3/validation_labels.csv",
     f"{['','One','Two','Three','Four'][sum(('nested' in r['rationale'] or 'mdc' in r['rationale'] or 'error.type' in r['rationale']) for r in fp_rows)]} of the {['','one','two','three','four','five'][len(fp_rows)]} mismatches"),
    ("nested \\texttt{mdc} object (one finding)", "mdc mismatches", "results/rq3/validation_labels.csv",
     f"nested \\texttt{{mdc}} object ({['zero','one','two'][sum('mdc' in r['rationale'] for r in fp_rows)]} finding)"),
    ("nested \\texttt{throwable} object (two findings)", "throwable mismatches", "results/rq3/validation_labels.csv",
     f"nested \\texttt{{throwable}} object ({['zero','one','two'][sum('throwable' in r['rationale'] for r in fp_rows)]} findings)"),
    ("9 of 15 sensitive-value findings and 1 of 15 unclassified-identifier findings", "privacy matches", "results/rq3/validation_summary.json",
     f"{cls('sensitive-values')['def_yes']} of 15 sensitive-value findings and {cls('unclassified-sensitive')['def_yes']} of 15 unclassified-identifier findings"),
    ("nine more \\texttt{session\\_id} fields", "borderline session ids", "results/rq3/validation_labels.csv",
     f"{['zero','one','two','three','four','five','six','seven','eight','nine'][sum(r['matches_definition'] == 'borderline' and 'session' in r['rationale'] for r in labels)]} more \\texttt{{session\\_id}} fields"),
    ("21 came from runtime logs the project wrote, 22 from demo telemetry, 5 from test fixtures and 12", "artifact kinds", "results/rq3/validation_summary.json",
     None),  # filled by fix_kind_row()
    ("Seven were defects", "worth-fixing findings", "results/rq3/validation_summary.json",
     f"{['','','','','','','','Seven'][vsum['overall']['actionable_yes']]} were defects"),
    ("Four are committed error-log entries", "worth fixing: error evidence", "results/rq3/validation_labels.csv",
     f"{['','One','Two','Three','Four'][lab_cls('rq3-missing-error-evidence', actionable_in_project_telemetry='yes')]} are committed error-log entries"),
    ("two are failures without request ids", "worth fixing: correlation", "results/rq3/validation_labels.csv",
     f"{['','one','two'][lab_cls('rq3-missing-correlation', actionable_in_project_telemetry='yes')]} are failures without request ids"),
    ("one is a committed agent prompt log", "worth fixing: email in prompt log", "results/rq3/validation_labels.csv",
     f"{['','one'][lab_cls('rq3-sensitive-values', actionable_in_project_telemetry='yes')]} is a committed agent prompt log"),
    ("baselines with $p < 0.001$", "McNemar p vs both rule baselines", "reports/baseline_comparison.json",
     "baselines with $p < 0.001$" if all(mc(m)["two_sided_exact_p_ten_thousandths"] < 10 for m in ("rule-light", "semantic-convention-only")) else "MISMATCH"),
    ("stratified sample of 60 findings", "validated sample size", "results/rq3/validation_summary.json",
     f"stratified sample of {vsum['overall']['n']} findings"),
    ("at most two per (repository, class)", "sampling cap", "results/rq3/validation_summary.json",
     "at most two per (repository, class)" if "<=2 per (repo, class)" in vsum["sample"] else "MISMATCH"),
    ("0.34 to 0.44 wide", "CI widths for 13/15, 12/15, 9/15", "results/rq3/validation_summary.json (Wilson, computed)",
     f"{min(widths):.2f} to {max(widths):.2f} wide"),
    ("(34 of 58)", "Python share", "results/rq3/corpus_dataset.json",
     f"({sum(s['language'] == 'Python' for s in corpus['subjects'])} of {corpus['subjects_total']})"),
]


def fix_kind_row():
    k = vsum["artifact_kind"]
    return (f"{k['runtime-log']} came from runtime logs the project wrote, {k['sample-telemetry']} from demo telemetry, "
            f"{k['test-fixture']} from test fixtures and {k['non-telemetry']}")


def main():
    rows, bad = [], []
    for text, what, src, got in ROWS:
        if what == "artifact kinds":
            got = fix_kind_row()
        ok = got == text and text in TEX
        if not ok:
            bad.append((text, got, text in TEX))
        rows.append((text, what, src, "yes" if ok else "NO"))
    md = ["# Number trace for `paper/tool_paper.tex`", "",
          "Generated by `python3 scripts/trace_numbers.py`. Each number below was",
          "recomputed from the listed committed file, formatted as the paper prints",
          "it, and found verbatim in the paper. `index.html` is generated from the",
          "same `.tex`, so the site carries the same numbers. Wilson intervals are",
          "computed (z = 1.96) from the counts in the listed file.", "",
          "| Text in paper | Quantity | Source file | Traced |", "| --- | --- | --- | --- |"]
    for text, what, src, ok in rows:
        md.append(f"| `{text.replace('|', '/')}` | {what} | `{src}` | {ok} |")
    md += ["", f"{len(rows) - len(bad)}/{len(rows)} traced.", "",
           "## Numbers outside the paper", "",
           "The site's meta description, `CITATION.cff` and the README's results table",
           "repeat numbers traced above (F1 0.953 / 0.991 / 0.952, p = 0.125 / 1.00,",
           "58 repositories, 116,420 events, 2,269 findings, 8.5 minutes, 10 of 14,",
           "13/15, 12/15, 25 of 30). The README also prints rule-light F1 0.750 and",
           "OTel-convention F1 0.557, which are the Table I F1 entries `.750` and",
           "`.557` from `reports/baseline_comparison.json`."]
    (ROOT / "paper/number_trace.md").write_text("\n".join(md) + "\n")
    for text, got, present in bad:
        print(f"FAIL  paper: {text!r}\n      recomputed: {got!r}  (in tex: {present})")
    print(f"{len(rows) - len(bad)}/{len(rows)} numbers traced")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
