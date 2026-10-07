"""Static checks on the generated paper site (no browser needed).

    python3 scripts/check_site.py

1. index.html is well-formed: every non-void tag is closed in order.
2. Every local href/src (PDF, LaTeX) exists in the repo; every #fragment
   resolves to an id on the page.
3. All required Scholar / Open Graph tags are present and non-empty.
4. The References section matches the PDF's bibliography entry for entry
   (pdftotext text, whitespace and hyphenation normalised).
5. Overflow risk: no external assets, the viewport meta is set, and the
   stylesheet wraps long tokens (overflow-wrap:anywhere on text, pre-wrap on
   <pre>, scrollable table wrappers).
Exits non-zero on any failure.
"""
import html.parser, pathlib, re, subprocess, sys, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAGE = ROOT / "index.html"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}
REQUIRED = ["citation_title", "citation_author", "citation_publication_date",
            "citation_pdf_url", "citation_abstract_html_url",
            "citation_fulltext_html_url", "citation_language", "description"]
REQUIRED_OG = ["og:title", "og:description", "og:type", "og:url"]

failures = []


class P(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.hrefs, self.meta, self.og = [], set(), [], {}, {}
        self.canonical = None
        self.refs, self._in_ref, self._buf = [], 0, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in VOID:
            self.stack.append((tag, self.getpos()))
        if "id" in a:
            if a["id"] in self.ids:
                failures.append(f"duplicate id {a['id']}")
            self.ids.add(a["id"])
        for k in ("href", "src"):
            if k in a and tag != "link":
                self.hrefs.append(a[k])
        if tag == "meta" and "name" in a:
            self.meta[a["name"]] = a.get("content", "")
        if tag == "meta" and "property" in a:
            self.og[a["property"]] = a.get("content", "")
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href")
        if tag == "li" and a.get("id", "").startswith("ref-"):
            self._in_ref, self._buf = len(self.stack), []

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1][0] != tag:
            failures.append(f"unbalanced </{tag}> at {self.getpos()}; open: "
                            f"{self.stack[-1] if self.stack else None}")
            return
        if self._in_ref and len(self.stack) == self._in_ref and tag == "li":
            self.refs.append("".join(self._buf)); self._in_ref = 0
        self.stack.pop()

    def handle_data(self, d):
        if self._in_ref:
            self._buf.append(d)


def norm(t):
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("“", '"').replace("”", '"').replace("’", "'")
    t = t.replace("–", "-").replace("—", "-")
    t = t.replace("-", "")               # pdftotext drops hyphens at line breaks
    return re.sub(r"\s+", "", t).lower()


def main():
    text = PAGE.read_text()
    p = P(); p.feed(text); p.close()
    if p.stack:
        failures.append(f"unclosed tags: {p.stack[:5]}")
    for h in p.hrefs:
        if h.startswith("#"):
            if h[1:] not in p.ids:
                failures.append(f"dangling fragment {h}")
        elif not re.match(r"https?://|mailto:", h):
            if not (ROOT / h).is_file():
                failures.append(f"local link target missing: {h}")
        elif not h.startswith("https://"):
            failures.append(f"non-https link {h}")
    for k in REQUIRED:
        if not p.meta.get(k):
            failures.append(f"missing meta {k}")
    for k in REQUIRED_OG:
        if not p.og.get(k):
            failures.append(f"missing {k}")
    if not p.canonical:
        failures.append("missing canonical link")
    if "citation_doi" in p.meta and not p.meta["citation_doi"]:
        failures.append("empty citation_doi")
    pdf_url = p.meta.get("citation_pdf_url", "")
    rel = pdf_url.split("/telemetry-contract-semantics/", 1)[-1]
    if not (ROOT / rel).is_file():
        failures.append(f"citation_pdf_url path not in repo: {rel}")

    # 4. references vs the PDF
    pdf = subprocess.run(["pdftotext", str(ROOT / "paper/tool_paper.pdf"), "-"],
                         capture_output=True, text=True, check=True).stdout
    tail = pdf.rsplit("REFERENCES", 1)[-1]
    pdf_refs = re.split(r"\n\s*\[(\d+)\]\s", "\n" + tail)
    pdf_map = {int(pdf_refs[i]): pdf_refs[i + 1] for i in range(1, len(pdf_refs) - 1, 2)}
    html_refs = [re.sub(r"^\[\d+\]", "", r) for r in p.refs]
    if len(html_refs) != len(pdf_map):
        failures.append(f"reference count: html {len(html_refs)} vs pdf {len(pdf_map)}")
    for i, r in enumerate(html_refs, 1):
        a, b = norm(r), norm(pdf_map.get(i, ""))
        if a != b:
            failures.append(f"reference [{i}] differs from PDF:\n  html {r[:120]}\n  pdf  {pdf_map.get(i, '')[:120]}")

    # 5. overflow / self-containment
    if re.search(r'<(script|link|img)[^>]+(src|href)="https?://', text) and \
            not re.search(r'<link rel="canonical"', text):
        failures.append("external asset referenced")
    for tag in re.findall(r'<(?:script|img|iframe)[^>]+src="([^"]+)"', text):
        failures.append(f"external/embedded asset src {tag[:60]}")
    for tag in re.findall(r'<link[^>]+rel="stylesheet"[^>]*>', text):
        failures.append(f"external stylesheet {tag[:60]}")
    if 'name="viewport"' not in text:
        failures.append("missing viewport meta")
    for rule in ("overflow-wrap:anywhere", "white-space:pre-wrap", ".tw{overflow-x:auto"):
        if rule not in text:
            failures.append(f"stylesheet lacks {rule}")
    body_text = re.sub(r"<[^>]+>", " ", text.split("<main>", 1)[1].split("</main>", 1)[0])
    long = sorted({t for t in body_text.split() if len(t) > 30})
    print(f"long tokens (>30 chars, wrapped by overflow-wrap:anywhere): {len(long)}")
    for t in long:
        print("   ", t[:90])

    print(f"ids {len(p.ids)}, links {len(p.hrefs)}, references {len(html_refs)} "
          f"(pdf {len(pdf_map)}), meta {sorted(k for k in p.meta if k.startswith('citation_'))}")
    if failures:
        print("FAIL"); [print(" -", f) for f in failures]; sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
