"""Render index.html (and sitemap.xml) from paper/tool_paper.tex.

The page is the whole paper as HTML: abstract, sections, both tables, the
bibliography exactly as IEEEtran.bst typesets it in the PDF (read from the
.bbl that BibTeX writes), a contents rail generated from the headings, a banner
linking the PDF, the LaTeX and the code, and a "Cite this paper" block.

The <head> carries Highwire Press `citation_*` tags, which is what Google
Scholar reads to index a paper hosted on a personal site. The PDF they point at
is served from this same site, and the author name matches the PDF's first
page.

    python3 build_site.py            # runs latexmk, then writes the page
    python3 build_site.py --no-latex # reuse the existing PDF and .bbl

Needs pandoc and, unless --no-latex, a TeX installation with IEEEtran. The page
loads no external assets, so opening index.html locally renders it exactly as
GitHub Pages will.
"""
import html, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
PAPER = HERE / "paper"
TEX = PAPER / "tool_paper.tex"
BBL = PAPER / "tool_paper.bbl"

TITLE = "Checking Failure-Path Telemetry in the Data a Project Already Emits"
AUTHOR = "Halley Young"            # as on the PDF; Scholar matches the two
AUTHOR_CITATION = "Young, Halley"  # surname-first form for citation_author
DATE_SHOWN = "October 2026"
PUB_DATE = "2026/10/07"            # citation_publication_date, YYYY/MM/DD
LASTMOD = "2026-10-07"             # sitemap <lastmod>
SITE_URL = "https://thehalleyyoung.github.io/telemetry-contract-semantics/"
PDF_PATH = "paper/tool_paper.pdf"
TEX_PATH = "paper/tool_paper.tex"
PDF_URL = SITE_URL + PDF_PATH
REPO_URL = "https://github.com/thehalleyyoung/telemetry-contract-semantics"

# ---------------------------------------------------------------------------
# DOI PLACEHOLDER. Leave empty until the DOI is minted, then paste it here
# (bare form, e.g. "10.5281/zenodo.1234567") and rerun this script. When set,
# it adds a citation_doi tag, a DOI line in the citation block, and a doi field
# in the BibTeX. While empty, none of those are emitted.
DOI = ""
# ---------------------------------------------------------------------------

# One-paragraph summary for search snippets (meta description, og:description).
# Keep it in step with the abstract and with CITATION.cff.
DESCRIPTION = (
    "telemetry-contracts is a pure-Python command-line tool that checks the "
    "logs, traces and metrics a project already emits for failure-path gaps: "
    "failures with no correlation id and failures with no error evidence. On "
    "60 findings sampled from a scan of 58 public repositories, the two "
    "failure-path checks matched their definitions in 25 of 30 cases. On a "
    "112-item gold set it reaches F1 0.953, against 0.991 and 0.952 for two "
    "zero-shot LLMs, with no significant difference. Preprint, not peer "
    "reviewed.")


def bibtex() -> str:
    doi = f"  doi          = {{{DOI}}},\n" if DOI else ""
    return ("@misc{young2026telemetry,\n"
            f"  title        = {{{{{TITLE}}}}},\n"
            f"  author       = {{{AUTHOR_CITATION}}},\n"
            "  year         = {2026},\n"
            "  month        = oct,\n"
            "  note         = {Preprint, not peer reviewed},\n"
            f"{doi}"
            f"  url          = {{{SITE_URL}}},\n"
            f"  howpublished = {{\\url{{{REPO_URL}}}}}\n"
            "}")


NAV_CSS = """
/* --- section navigation, generated from the paper's own headings --- */
.layout{display:grid;grid-template-columns:15.5rem minmax(0,46rem);gap:2.6rem;
justify-content:center;padding:2.4rem 1.2rem 6rem}
.toc{position:sticky;top:2rem;align-self:start;max-height:calc(100vh - 4rem);
overflow-y:auto;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
font-size:.83rem;line-height:1.45;border-right:1px solid var(--rule);padding-right:1.1rem}
.toc h2{font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
margin:0 0 .7rem;border:0;padding:0}
.toc ol{list-style:none;margin:0;padding:0}
.toc li{margin:.12rem 0}
.toc li.sub{padding-left:.85rem;font-size:.79rem}
.toc a{display:block;padding:.2rem .35rem;border-radius:3px;color:var(--muted);
text-decoration:none;border-left:2px solid transparent}
.toc a:hover{color:var(--fg);background:var(--stripe)}
.toc a.here{color:var(--accent);border-left-color:var(--accent);background:var(--stripe)}
.toc .sec{color:var(--fg)}
main{max-width:none;margin:0;padding:0;min-width:0}
html{scroll-behavior:smooth}
:target{scroll-margin-top:1.5rem}
h2,h3{scroll-margin-top:1.5rem}
@media (max-width:62rem){
  .layout{display:block;max-width:46rem;margin:0 auto}
  .toc{position:static;max-height:none;border-right:0;border-bottom:1px solid var(--rule);
  padding:0 0 1rem;margin-bottom:2rem;columns:2;column-gap:1.6rem}
  .toc li.sub{display:none}
}
@media print{.toc{display:none}.layout{display:block}}
"""

NAV_JS = """
<script>
(function () {
  var links = [].slice.call(document.querySelectorAll('.toc a'));
  var targets = links.map(function (a) {
    return document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
  });
  var current = -1;
  function mark() {
    var best = 0;
    for (var i = 0; i < targets.length; i++) {
      if (targets[i] && targets[i].getBoundingClientRect().top <= 90) best = i;
    }
    if (best === current) return;
    if (current >= 0) links[current].classList.remove('here');
    links[best].classList.add('here');
    current = best;
  }
  addEventListener('scroll', mark, {passive: true});
  addEventListener('resize', mark, {passive: true});
  addEventListener('load', mark);
  mark();
})();
</script>
"""

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV"]


def pandoc(latex: str) -> str:
    return subprocess.run(
        ["pandoc", "-f", "latex", "-t", "html5", "--mathml",
         "--shift-heading-level-by=1", "--wrap=none"],
        input=latex, capture_output=True, text=True, check=True).stdout


def read_bbl():
    """[(key, latex)] in the order IEEEtran numbers them in the PDF."""
    text = BBL.read_text()
    body = text.split("\\BIBdecl", 1)[1].split("\\end{thebibliography}", 1)[0]
    items = re.split(r"\\bibitem\{([^}]+)\}", body)[1:]
    return [(items[i], items[i + 1].strip()) for i in range(0, len(items), 2)]


def ref_html(latex: str) -> str:
    latex = latex.replace("\\newblock", " ")
    latex = re.sub(r"\\BIBentry(ALT|STD)interwordspacing", "", latex)
    latex = re.sub(r"\\url\{([^}]*)\}", r"\\href{\1}{\1}", latex)
    out = pandoc(latex).strip()
    out = re.sub(r"^<p>(.*)</p>$", r"\1", out, flags=re.S)
    out = out.replace("\u0131\u0301", "\u00ed")   # {\'\i} -> one code point
    return re.sub(r"\s+", " ", out)


def number_labels(src: str):
    """Compute the numbers IEEEtran prints for \\label targets: sections in
    Roman, subsections as "IV-C", tables in Roman."""
    labels, sec, sub, tab = {}, 0, 0, 0
    tokens = re.finditer(
        r"\\(section|subsection)(\*?)\{|\\begin\{table\}|\\label\{([^}]+)\}", src)
    last = None
    for m in tokens:
        if m.group(1) == "section" and not m.group(2):
            sec += 1; sub = 0; last = ROMAN[sec]
        elif m.group(1) == "subsection" and not m.group(2):
            sub += 1; last = f"{ROMAN[sec]}-{chr(64 + sub)}"
        elif m.group(0).startswith("\\begin{table}"):
            tab += 1; last = ROMAN[tab]
        elif m.group(3):
            labels[m.group(3)] = last
    return labels


def preprocess(src: str, order: dict, labels: dict) -> str:
    """Rewrite the LaTeX so pandoc renders it the way the PDF reads."""
    src = re.sub(r"\\tool(?![a-zA-Z])", r"\\textsc{telemetry-contracts}", src)
    src = re.sub(r"\\path\{([^}]*)\}", r"\\texttt{\1}", src)
    src = src.replace(r"\footnotesize\setlength{\tabcolsep}{3pt}", "")
    src = src.replace("$<$", r"\textless{}").replace("$p$", r"\emph{p}")

    def cite(m):
        keys = [k.strip() for k in m.group(1).split(",")]
        return ", ".join(f"\\href{{#ref-{k}}}{{[{order[k]}]}}" for k in keys)
    src = re.sub(r"~?\\cite\{([^}]+)\}", lambda m: "~" + cite(m), src)
    src = re.sub(r"\\ref\{([^}]+)\}",
                 lambda m: f"\\hyperref[{m.group(1)}]{{{labels[m.group(1)]}}}", src)

    sec, sub = 0, 0
    def heading(m):
        nonlocal sec, sub
        kind, star, text = m.group(1), m.group(2), m.group(3)
        if star:
            return m.group(0)
        if kind == "section":
            sec += 1; sub = 0
            return f"\\section{{{ROMAN[sec]}. {text}}}"
        sub += 1
        return f"\\subsection{{{chr(64 + sub)}. {text}}}"
    src = re.sub(r"\\(section|subsection)(\*?)\{([^}]*)\}", heading, src)

    tab = 0
    def caption(m):
        nonlocal tab
        tab += 1
        return f"\\caption{{Table {ROMAN[tab]}. "
    src = re.sub(r"\\caption\{", caption, src)
    return src


def build_toc(body: str) -> str:
    items = re.findall(r'<h([23]) id="([^"]+)"[^>]*>(.*?)</h[23]>', body, re.S)
    rows = []
    for level, hid, raw in items:
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", raw)).strip()
        if text.lower() == "abstract":
            continue
        cls, li = ("sec", "") if level == "2" else ("", "sub")
        rows.append(f'<li class="{li}"><a class="{cls}" href="#{hid}">{text}</a></li>')
    return ('<nav class="toc" aria-label="Contents"><h2>Contents</h2><ol>'
            + "".join(rows) + "</ol></nav>")


def head_meta() -> str:
    esc = lambda t: html.escape(t, quote=True)
    tags = [
        ("citation_title", TITLE),
        ("citation_author", AUTHOR_CITATION),
        ("citation_publication_date", PUB_DATE),
        ("citation_pdf_url", PDF_URL),
    ]
    if DOI:
        tags.append(("citation_doi", DOI))
    tags += [
        ("citation_abstract_html_url", SITE_URL),
        ("citation_fulltext_html_url", SITE_URL),
        ("citation_language", "en"),
        ("description", DESCRIPTION),
        ("author", AUTHOR),
    ]
    out = [f'<meta name="{k}" content="{esc(v)}">' for k, v in tags]
    out += [f'<meta property="og:title" content="{esc(TITLE)}">',
            f'<meta property="og:description" content="{esc(DESCRIPTION)}">',
            '<meta property="og:type" content="article">',
            f'<meta property="og:url" content="{SITE_URL}">',
            '<meta property="og:locale" content="en_US">',
            f'<link rel="canonical" href="{SITE_URL}">']
    return "\n".join(out) + "\n"


def cite_block() -> str:
    doi = (f' <a href="https://doi.org/{DOI}">https://doi.org/{DOI}</a>.'
           if DOI else "")
    return ('<h2 id="cite">Cite this paper</h2>\n'
            f'<p>Young, H. (2026). <em>{TITLE}</em>. Preprint, not peer '
            f'reviewed. <a href="{SITE_URL}">{SITE_URL}</a>.{doi}</p>\n'
            f'<pre><code>{html.escape(bibtex(), quote=False)}</code></pre>\n')


def main():
    if "--no-latex" not in sys.argv:
        subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode",
                        TEX.name], cwd=PAPER, check=True,
                       stdout=subprocess.DEVNULL)
    if not BBL.is_file():
        raise SystemExit("paper/tool_paper.bbl missing: run without --no-latex")

    tex = TEX.read_text()
    refs = read_bbl()
    order = {k: i + 1 for i, (k, _) in enumerate(refs)}
    doc = tex.split("\\begin{document}", 1)[1].split("\\bibliographystyle", 1)[0]
    labels = number_labels(doc)
    abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", doc, re.S).group(1)
    sections = doc.split("\\maketitle", 1)[1].split("\\end{abstract}", 1)[1]

    abstract_html = pandoc(preprocess(abstract, order, labels))
    body = pandoc(preprocess(sections, order, labels))
    body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")

    ref_items = "\n".join(
        f'<li id="ref-{k}"><span class="n">[{i + 1}]</span><span>{ref_html(v)}</span></li>'
        for i, (k, v) in enumerate(refs))
    body += f'<h2 id="references">References</h2>\n<ol class="refs">\n{ref_items}\n</ol>\n'
    body += cite_block()

    toc = build_toc(body)
    css = (HERE / "site.css").read_text()
    header = (f'<header class="paper-head">\n<h1>{TITLE}</h1>\n'
              f'<p class="byline">{AUTHOR} &middot; {DATE_SHOWN} &middot; '
              'preprint, not peer reviewed</p>\n</header>')
    banner = (f'<div class="banner">Paper: <a href="{PDF_PATH}">PDF</a> &middot; '
              f'<a href="{TEX_PATH}">LaTeX</a> &middot; '
              f'<a href="{REPO_URL}">code &amp; data</a></div>')
    page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{TITLE}</title>\n' + head_meta() +
            f'<style>{css}{NAV_CSS}</style>\n</head>\n<body>\n'
            f'<div class="layout">\n{toc}\n<main>\n{header}\n{banner}\n'
            f'<h2 id="abstract">Abstract</h2>\n{abstract_html}\n{body}\n'
            '</main>\n</div>\n' + NAV_JS + '</body>\n</html>\n')
    (HERE / "index.html").write_text(page)

    (HERE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE_URL}</loc><lastmod>{LASTMOD}</lastmod></url>\n'
        f'  <url><loc>{PDF_URL}</loc><lastmod>{LASTMOD}</lastmod></url>\n'
        '</urlset>\n')
    print(f"index.html written ({len(refs)} references, "
          f"{body.count('<table')} tables); sitemap.xml written")


if __name__ == "__main__":
    main()
