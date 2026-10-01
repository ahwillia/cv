"""Fetch an author's records from DBLP via its SPARQL endpoint.

DBLP is the best source for CS conference papers (NeurIPS, ICLR, ...), which
OpenAlex often misses or lists without a venue. The regular dblp.org API sits
behind a bot challenge; sparql.dblp.org does not.
"""

import json
import re
import urllib.parse
import urllib.request
from collections import defaultdict

ENDPOINT = "https://sparql.dblp.org/sparql"
USER_AGENT = "cv-maker/0.1 (https://github.com/ahwillia/cv)"

QUERY = """
PREFIX dblp: <https://dblp.org/rdf/schema#>
SELECT ?pub ?type ?title ?year ?venue ?doi ?page ?ord ?name ?creator WHERE {
  ?pub dblp:authoredBy <https://dblp.org/pid/%s> ;
       a ?type ; dblp:title ?title ; dblp:yearOfPublication ?year ;
       dblp:hasSignature ?sig .
  FILTER(?type IN (dblp:Inproceedings, dblp:Article, dblp:Informal))
  ?sig dblp:signatureOrdinal ?ord ; dblp:signatureDblpName ?name .
  OPTIONAL { ?sig dblp:signatureCreator ?creator }
  OPTIONAL { ?pub dblp:publishedIn ?venue }
  OPTIONAL { ?pub dblp:doi ?doi }
  OPTIONAL { ?pub dblp:primaryDocumentPage ?page }
}
"""


def _query(q: str) -> list[dict]:
    req = urllib.request.Request(
        ENDPOINT,
        data=urllib.parse.urlencode({"query": q}).encode(),
        headers={"Accept": "application/sparql-results+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        rows = json.load(r)["results"]["bindings"]
    return [{k: v["value"] for k, v in row.items()} for row in rows]


def short_name(dblp_name: str) -> str:
    """'Alex H. Williams' -> 'Williams AH'. Drops DBLP homonym suffixes ('Wei Zhou 0003')."""
    name = re.sub(r"\s+\d{4}$", "", dblp_name)
    parts = name.replace(".", " ").split()
    if len(parts) < 2:
        return name
    initials = "".join(seg[0].upper() for g in parts[:-1] for seg in g.split("-") if seg)
    return f"{parts[-1]} {initials}"


def paper_url(page: str | None) -> str | None:
    """Landing page for the paper; old NeurIPS links are moved to the current host."""
    if not page:
        return None
    return re.sub(r"^https?://papers\.nips\.cc/paper_files/", "https://proceedings.neurips.cc/paper_files/", page)


def fetch(pid: str, self_name: str, venue_names: dict) -> list[dict]:
    """Return normalized works (see pubs.py) for DBLP person `pid`.

    Conference venues keep DBLP's abbreviation (NeurIPS, ICLR, ...), which is the
    key into data/venues.yaml; journal abbreviations are expanded via `venue_names`."""
    me = f"https://dblp.org/pid/{pid}"
    pubs: dict[str, dict] = {}
    sigs: dict[str, dict[int, str]] = defaultdict(dict)
    for row in _query(QUERY % pid):
        p = pubs.setdefault(row["pub"], dict(row))
        for k in ("venue", "doi", "page"):  # OPTIONAL fields may be missing on some rows
            if not p.get(k) and row.get(k):
                p[k] = row[k]
        name = self_name if row.get("creator") == me else short_name(row["name"])
        sigs[row["pub"]][int(row["ord"])] = name

    works = []
    for key, p in pubs.items():
        kind = p["type"].rsplit("#", 1)[1]
        venue = p.get("venue")
        doi = (p.get("doi") or "").removeprefix("https://doi.org/").lower() or None
        if kind == "Informal" or venue == "CoRR":
            kind, venue = "preprint", "arXiv"
        else:
            kind = "conference" if kind == "Inproceedings" else "journal"
            if kind == "journal":
                venue = venue_names.get(venue, venue)
        arxiv = re.match(r"10\.48550/arxiv\.(.+)", doi or "")
        works.append({
            "source": "dblp",
            "key": key,
            "title": p["title"].rstrip("."),
            "year": int(p["year"]),
            "kind": kind,
            "venue": venue,
            "details": arxiv.group(1) if arxiv else None,
            "doi": doi,
            "authors": [sigs[key][i] for i in sorted(sigs[key])],
            "url": paper_url(p.get("page")) if kind == "conference" else None,
        })
    return works
