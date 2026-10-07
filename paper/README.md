# Paper

`tool_paper.tex` is the preprint "Checking Failure-Path Telemetry in the Data a
Project Already Emits" by Halley Young. Build it with:

```bash
cd paper && latexmk -pdf tool_paper.tex
```

The HTML version at the repository root (`index.html`) is generated from the
same source by `python3 build_site.py`.

* `references.bib`: every entry is checked mechanically against Crossref, the
  arXiv API or the publisher page by `python3 scripts/check_references.py`;
  the result is `reference_check.json`.
* `number_trace.md` lists every number in the paper and the committed file it
  comes from. The commands that regenerate those files are in
  `../REPRODUCE.md`.
