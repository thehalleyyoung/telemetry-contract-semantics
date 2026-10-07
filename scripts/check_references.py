"""Check every entry of paper/references.bib against an external record.

    python3 scripts/check_references.py   # writes paper/reference_check.json

For each entry the script fetches one authoritative record and compares it with
the .bib fields:
  * DOI present      -> Crossref /works/{doi}
  * arXiv eprint     -> arXiv export API
  * otherwise        -> the publisher / project page of the work, whose text
                        must contain the title, every .bib author surname and
                        the .bib year. (DBLP sits behind a bot challenge and
                        OpenAlex dates the OSDI'12 paper from a CiteSeerX copy,
                        so neither is used.)
Title match: normalised token Jaccard >= 0.9 (case, punctuation, LaTeX braces
ignored). Authors: every .bib surname must appear among the record's authors,
and the counts must agree. Year must be equal. An entry passes only if every
comparison it can make passes. Exits non-zero if any entry fails.
"""
import json, pathlib, re, sys, time, unicodedata, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIB = ROOT / "paper" / "references.bib"
OUT = ROOT / "paper" / "reference_check.json"
UA = {"User-Agent": "telemetry-contracts-refcheck/1.0 (+https://github.com/thehalleyyoung/telemetry-contract-semantics)"}

# Entries no bibliographic database indexes: the page that is the work itself.
PAGES = {
    "yuan2012conservative": "https://www.usenix.org/conference/osdi12/technical-sessions/presentation/yuan",
    "sigelman2010dapper": "https://research.google/pubs/dapper-a-large-scale-distributed-systems-tracing-infrastructure/",
    "otel-semconv": "https://opentelemetry.io/docs/specs/semconv/",
}


def get(url, accept=None):
    h = dict(UA)
    if accept:
        h["Accept"] = accept
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(2 * (attempt + 1))
    raise err


def parse_bib(text):
    entries = []
    for m in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", text, re.S):
        fields = {}
        for f in re.finditer(r"(\w+)\s*=\s*(\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}|\d+)", m.group(3)):
            v = f.group(2)
            fields[f.group(1).lower()] = v[1:-1] if v.startswith("{") else v
        entries.append({"type": m.group(1).lower(), "key": m.group(2).strip(), **fields})
    return entries


def delatex(s):
    s = re.sub(r"\\['`^\"~]\{?\\?([a-zA-Z])\}?", r"\1", s)
    return s.replace("{", "").replace("}", "").replace("\\", "")


def toks(s):
    s = unicodedata.normalize("NFKD", delatex(s)).encode("ascii", "ignore").decode().lower()
    return set(re.findall(r"[a-z0-9]+", s))


def jacc(a, b):
    a, b = toks(a), toks(b)
    return len(a & b) / max(1, len(a | b))


def surname(name):
    name = delatex(name).strip()
    if "," in name:
        return name.split(",")[0].strip()
    parts = name.split()
    return parts[-1] if parts else name


def fold(s):
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower())


def bib_authors(e):
    a = e.get("author", "")
    if a.startswith("{") or a.startswith("OpenTelemetry"):
        return []
    return [surname(x) for x in re.split(r"\s+and\s+", a)]


def compare(e, rec):
    res = {"record_title": rec["title"], "record_year": rec.get("year"),
           "record_authors": rec.get("authors"), "source": rec["source"], "url": rec["url"]}
    res["title_similarity"] = round(jacc(e["title"], rec["title"]), 3)
    ok = res["title_similarity"] >= 0.9
    if rec.get("year") is not None and e.get("year"):
        res["year_match"] = int(e["year"]) == int(rec["year"])
        ok &= res["year_match"]
    ba = bib_authors(e)
    if ba and rec.get("authors"):
        rs = {fold(surname(x)) for x in rec["authors"]}
        rfull = fold(" ".join(rec["authors"]))
        missing = [s for s in ba if fold(s) not in rs and fold(s) not in rfull]
        res["authors_missing_from_record"] = missing
        res["author_count"] = [len(ba), len(rec["authors"])]
        ok &= not missing and len(ba) == len(rec["authors"])
    res["pass"] = bool(ok)
    return res


def crossref(doi):
    j = json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"]
    year = (j.get("published-print") or j.get("published-online") or j.get("issued"))["date-parts"][0][0]
    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in j.get("author", [])]
    title = j["title"][0] + (": " + j["subtitle"][0] if j.get("subtitle") else "")
    return {"title": title, "year": year, "authors": authors,
            "source": "crossref", "url": "https://doi.org/" + doi}


def arxiv(aid):
    x = get("http://export.arxiv.org/api/query?id_list=" + aid)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    ent = ET.fromstring(x).find("a:entry", ns)
    return {"title": " ".join(ent.find("a:title", ns).text.split()),
            "year": int(ent.find("a:published", ns).text[:4]),
            "authors": [a.find("a:name", ns).text for a in ent.findall("a:author", ns)],
            "source": "arxiv", "url": "https://arxiv.org/abs/" + aid}


def page(key, e):
    url = PAGES[key]
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", get(url)))
    t = delatex(e["title"])
    res = {"source": "publisher-page", "url": url,
           "title_found_on_page": fold(t) in fold(text)}
    ok = res["title_found_on_page"]
    ba = bib_authors(e)
    if ba:
        res["authors_missing_from_page"] = [a for a in ba if fold(a) not in fold(text)]
        ok &= not res["authors_missing_from_page"]
    if e.get("year"):
        res["year_found_on_page"] = e["year"] in text or f"'{e['year'][2:]}" in text
        ok &= res["year_found_on_page"]
    res["pass"] = bool(ok)
    return res


def main():
    entries = parse_bib(BIB.read_text())
    out = {"checked_on": time.strftime("%Y-%m-%d"), "bib": "paper/references.bib",
           "method": __doc__.strip().splitlines()[2:], "entries": []}
    for e in entries:
        row = {"key": e["key"], "bib_title": delatex(e["title"]), "bib_year": e.get("year"),
               "bib_authors": bib_authors(e)}
        try:
            if e.get("doi"):
                rec = crossref(e["doi"])
            elif e.get("eprint"):
                rec = arxiv(e["eprint"])
            elif e["key"] in PAGES:
                row.update(page(e["key"], e)); rec = None
            else:
                raise ValueError("no DOI, eprint or page for this entry")
            if rec:
                row.update(compare(e, rec))
        except Exception as ex:  # noqa: BLE001
            row.update({"pass": False, "error": repr(ex)})
        out["entries"].append(row)
        print(f"{'PASS' if row['pass'] else 'FAIL'}  {e['key']:32s} "
              f"{row.get('source', '-'):8s} sim={row.get('title_similarity')}")
        time.sleep(0.5)
    n = sum(r["pass"] for r in out["entries"])
    out["summary"] = {"entries": len(entries), "pass": n, "fail": len(entries) - n}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"{n}/{len(entries)} entries verified -> {OUT.relative_to(ROOT)}")
    sys.exit(0 if n == len(entries) else 1)


if __name__ == "__main__":
    main()
