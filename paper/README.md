# Paper

`tool_paper.tex` is a tool-paper preprint: "Checking Failure-Path Telemetry in
the Data a Project Already Emits". It has not been submitted or accepted
anywhere. Build it with:

```bash
cd paper && latexmk -pdf tool_paper.tex
```

* `references.bib`: every entry was checked against Crossref, the publisher
  page, or arXiv on 2026-10-06. The record is in `bib_verification.json`.
* Every number in the paper comes from a committed raw output. The commands
  are in `../REPRODUCE.md`.

An earlier markdown outline in this file claimed the tool "significantly
outperforms" an LLM baseline. That baseline was a hand-written surrogate. With
real LLMs (claude-haiku-4.5 and gpt-4.1-mini) the tool shows no significant
difference, and Haiku scores higher. The outline has been replaced by the
`.tex` file.
