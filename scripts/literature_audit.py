"""Verify the bibliography and run a bounded, logged literature search.

    python -m scripts.literature_audit verify     # every DOI / arXiv id against Crossref or arXiv
    python -m scripts.literature_audit search     # fixed query strings against Crossref, logged with date

Writes ``results/research/literature_verification.json`` and
``results/research/literature_search_log.json``. Nothing here decides novelty:
the search log is screened by a person (or the session) afterwards, and the
screening decisions are recorded in ``docs/research/FINAL_NOVELTY_AND_PRIOR_ART_AUDIT.md``.

Only public scholarly metadata APIs are used, with a descriptive User-Agent and
no personal contact data.
"""
from __future__ import annotations

import difflib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIB = ROOT / "paper/conference_final/references.bib"
FULLTEXT = ROOT / "results/research/literature_fulltext_review.json"
VERIFY_OUT = ROOT / "results/research/literature_verification.json"
SEARCH_OUT = ROOT / "results/research/literature_search_log.json"
AGENT = "AirGuard-India-literature-audit/1.0 (academic project; https://github.com/nishaids/airguard-india)"

#: Official landing pages for entries whose BibTeX carries no identifier; the page title must contain the recorded title.
OFFICIAL_PAGES = {"xu2021": "https://proceedings.mlr.press/v139/xu21h.html"}

QUERIES = [
    "CAMS forecast post-processing station bias correction machine learning",
    "Copernicus Atmosphere Monitoring Service India PM2.5 forecast evaluation",
    "next-day air quality index forecasting India stations machine learning",
    "conformal prediction air quality forecasting uncertainty",
    "air quality early warning system India operational forecast",
    "censored extreme air pollution episodes forecast evaluation",
    "air pollution forecast warning false alarm missed event cost loss",
    "prospective verification operational air quality forecast",
    "quantile regression air quality forecast extreme pollution",
    "spatial cross-validation air quality model unseen stations transfer",
]


def get(url, accept="application/json"):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": accept})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            if error.code in (404, 400):
                return error.code, ""
            time.sleep(2 * (attempt + 1))
        except Exception:  # noqa: BLE001 - transport errors are retried, then recorded
            time.sleep(2 * (attempt + 1))
    return None, ""


def norm(text):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (text or "").lower().replace("{", "").replace("}", ""))).strip()


def bib_entries():
    text = BIB.read_text(encoding="utf-8")
    entries = []
    for match in re.finditer(r"@(\w+)\{([^,]+),(.*?)\n\}", text, re.S):
        kind, key, body = match.groups()
        fields = {k.lower(): v.strip() for k, v in re.findall(r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}", body)}
        entries.append({"key": key.strip(), "type": kind.lower(), **fields})
    return entries


def title_search(t):
    """No identifier recorded: look the exact title up (arXiv for proceedings, Crossref otherwise)."""
    title = norm(t["title"])
    if t.get("type") == "inproceedings":
        query = urllib.parse.quote('ti:"' + re.sub(r"[{}$\\_]", "", t["title"]) + '"')
        status, body = get(f"http://export.arxiv.org/api/query?search_query={query}&max_results=5", "application/atom+xml")
        found = [el.text for el in ET.fromstring(body).iter("{http://www.w3.org/2005/Atom}title")][1:] if status == 200 and body else []
        best = max(found, key=lambda f: difflib.SequenceMatcher(None, title, norm(f)).ratio(), default="")
        sim = round(difflib.SequenceMatcher(None, title, norm(best)).ratio(), 3)
        return {"found_title": best, "title_similarity": sim,
                "status": "VERIFIED_ARXIV_TITLE" if sim >= 0.9 else "NOT_VERIFIED",
                "note": "the work exists on arXiv under this title; the recorded venue was not checked against the proceedings"}
    params = {"query.bibliographic": re.sub(r"[{}]", "", t["title"]), "rows": 5, "select": "DOI,title,issued,container-title"}
    status, body = get("https://api.crossref.org/works?" + urllib.parse.urlencode(params))
    items = json.loads(body)["message"]["items"] if status == 200 else []
    scored = [(difflib.SequenceMatcher(None, title, norm((i.get("title") or [""])[0])).ratio(), i) for i in items]
    sim, item = max(scored, key=lambda s: s[0], default=(0, {}))
    year = (item.get("issued", {}).get("date-parts") or [[None]])[0][0] if item else None
    ok = sim >= 0.9 and str(year) == str(t.get("year"))
    return {"found_title": (item.get("title") or [""])[0] if item else None, "found_doi": item.get("DOI") if item else None, "found_year": year,
            "title_similarity": round(sim, 3), "status": "VERIFIED_BY_TITLE_SEARCH" if ok else "NOT_VERIFIED"}


def verify():
    targets = []
    for e in bib_entries():
        how = e.get("howpublished") or ""
        url = e.get("url") or (re.search(r"\\url\{([^}]+)\}", how) or [None, None])[1]
        targets.append({"source": "conference_bib", "key": e["key"], "title": e.get("title"), "year": e.get("year"),
                        "doi": e.get("doi"), "eprint": e.get("eprint") or (how if "arXiv" in how else None), "url": url, "type": e["type"],
                        "venue_recorded": e.get("journal") or e.get("booktitle") or e.get("institution")})
    for e in json.loads(FULLTEXT.read_text(encoding="utf-8"))["entries"]:
        targets.append({"source": "fulltext_review", "key": e["id"], "title": e["title"], "year": e.get("year"),
                        "doi": e.get("doi"), "url": (e.get("sources") or [None])[0]})
    results = []
    for t in targets:
        record = dict(t)
        if t.get("doi"):
            status, body = get("https://api.crossref.org/works/" + urllib.parse.quote(t["doi"].strip()))
            if status == 200:
                item = json.loads(body)["message"]
                found = (item.get("title") or [""])[0]
                record.update(found_title=found, found_year=(item.get("issued", {}).get("date-parts") or [[None]])[0][0],
                              venue=(item.get("container-title") or [None])[0],
                              first_author=((item.get("author") or [{}])[0]).get("family"),
                              title_similarity=round(difflib.SequenceMatcher(None, norm(t["title"]), norm(found)).ratio(), 3))
                record["status"] = "VERIFIED_DOI" if record["title_similarity"] >= 0.85 else "DOI_TITLE_MISMATCH"
            else:
                record["status"] = "DOI_NOT_FOUND" if status == 404 else "UNREACHABLE"
        else:
            arxiv = re.search(r"(\d{4}\.\d{4,5})", " ".join(str(t.get(k) or "") for k in ("eprint", "url")))
            if arxiv:
                status, body = get(f"http://export.arxiv.org/api/query?id_list={arxiv.group(1)}", "application/atom+xml")
                titles = [el.text for el in ET.fromstring(body).iter("{http://www.w3.org/2005/Atom}title")][1:] if status == 200 and body else []
                found = (titles or [""])[0]
                record.update(arxiv_id=arxiv.group(1), found_title=found,
                              title_similarity=round(difflib.SequenceMatcher(None, norm(t["title"]), norm(found)).ratio(), 3))
                record["status"] = "VERIFIED_ARXIV" if found and record["title_similarity"] >= 0.85 else "ARXIV_TITLE_MISMATCH"
            elif t.get("url"):
                status, _ = get(t["url"], "text/html")
                record["status"] = "URL_REACHABLE" if status == 200 else "URL_NOT_VERIFIED"
            elif t["key"] in OFFICIAL_PAGES:
                status, page = get(OFFICIAL_PAGES[t["key"]], "text/html")
                heading = norm((re.search(r"<title>([^<]*)", page or "") or [None, ""])[1])
                record.update(url=OFFICIAL_PAGES[t["key"]], found_title=heading,
                              status="VERIFIED_OFFICIAL_PAGE" if status == 200 and norm(t["title"]) in heading else "NOT_VERIFIED")
            else:
                record.update(title_search(t))
        results.append(record)
        time.sleep(0.4)
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out = {"generated_by": "scripts/literature_audit.py verify", "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "rule": "VERIFIED means the identifier resolves at Crossref/arXiv and the returned title matches the recorded title (similarity >= 0.85)",
           "counts": counts, "entries": results}
    VERIFY_OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return counts


def search():
    log = []
    for query in QUERIES:
        params = {"query.bibliographic": query, "filter": "from-pub-date:2018-01-01,type:journal-article", "rows": 20,
                  "select": "DOI,title,author,issued,container-title,abstract,type,is-referenced-by-count"}
        status, body = get("https://api.crossref.org/works?" + urllib.parse.urlencode(params))
        hits = []
        if status == 200:
            for item in json.loads(body)["message"]["items"]:
                hits.append({"doi": item.get("DOI"), "title": (item.get("title") or [""])[0],
                             "year": (item.get("issued", {}).get("date-parts") or [[None]])[0][0],
                             "venue": (item.get("container-title") or [None])[0],
                             "first_author": ((item.get("author") or [{}])[0]).get("family"),
                             "cited_by": item.get("is-referenced-by-count"),
                             "abstract": re.sub(r"<[^>]+>", " ", item.get("abstract") or "")[:1500]})
        log.append({"query": query, "database": "Crossref REST API (journal articles, 2018 onward)", "http_status": status, "hits": hits})
        time.sleep(1.0)
    out = {"generated_by": "scripts/literature_audit.py search", "searched_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "limitations": "One bibliographic database; top 20 relevance-ranked hits per query; journal articles only, so conference papers and preprints are covered only through the existing review",
           "queries": log}
    SEARCH_OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return {"queries": len(log), "hits": sum(len(q["hits"]) for q in log)}


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "verify"
    print(json.dumps(verify() if command == "verify" else search()))
