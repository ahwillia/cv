"""Fetch works attributed to an ORCID iD from OpenAlex.

ORCID's own record for this CV has no public works, so OpenAlex (which links
authors to ORCID via Crossref/arXiv/bioRxiv metadata) is the primary source.
"""

import json
import re
import urllib.parse
import urllib.request

API = "https://api.openalex.org/works"
FIELDS = "id,doi,title,publication_year,type,primary_location,locations,ids,authorships,biblio"

# Preprint servers / repositories, identified by DOI prefix.
PREPRINT_DOI_PREFIXES = {
    "10.48550": "arXiv",
    "10.1101": "bioRxiv",
    "10.64898": "bioRxiv",
    "10.5281": "Zenodo",
    "10.31234": "PsyArXiv",
    "10.21203": "Research Square",
}

VENUE_CLEANUP = {
    "arXiv (Cornell University)": "arXiv",
    "bioRxiv (Cold Spring Harbor Laboratory)": "bioRxiv",
}


def fetch(orcid: str) -> list[dict]:
    """Return every OpenAlex work with an author carrying `orcid`."""
    works, cursor = [], "*"
    while cursor:
        q = urllib.parse.urlencode({
            "filter": f"authorships.author.orcid:{orcid}",
            "per_page": 200,
            "cursor": cursor,
            "select": FIELDS,
        })
        with urllib.request.urlopen(f"{API}?{q}", timeout=60) as r:
            page = json.load(r)
        works += page["results"]
        cursor = page["meta"].get("next_cursor") if page["results"] else None
    return works


def doi_of(w: dict) -> str | None:
    d = w.get("doi")
    return d.removeprefix("https://doi.org/").lower() if d else None


def is_preprint_doi(doi: str | None) -> bool:
    return bool(doi) and doi.split("/")[0] in PREPRINT_DOI_PREFIXES


def arxiv_id(doi: str | None) -> str | None:
    m = re.match(r"10\.48550/arxiv\.(.+)", doi or "")
    return m.group(1) if m else None


def venue_of(w: dict) -> str | None:
    src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    doi = doi_of(w)
    if doi and doi.split("/")[0] in PREPRINT_DOI_PREFIXES:
        return PREPRINT_DOI_PREFIXES[doi.split("/")[0]]
    if src in ("PubMed", "PubMed Central", None):
        # Aggregator, not a venue: look for a real journal among other locations.
        for loc in w.get("locations") or []:
            name = (loc.get("source") or {}).get("display_name")
            if name and name not in ("PubMed", "PubMed Central"):
                src = name
                break
    return VENUE_CLEANUP.get(src, src)


def short_name(display_name: str) -> str:
    """'Alex H. Williams' -> 'Williams AH'; 'Jean-Paul Sartre' -> 'Sartre JP'."""
    name = re.sub(r"\(.*?\)|[()]", " ", display_name)
    parts = name.replace(".", " ").split()
    if len(parts) < 2:
        return display_name
    last, given = parts[-1], parts[:-1]
    initials = "".join(seg[0].upper() for g in given for seg in g.split("-") if seg)
    return f"{last} {initials}"


def authors_of(w: dict, orcid: str, self_name: str) -> list[str]:
    out = []
    for a in w.get("authorships") or []:
        au = a.get("author") or {}
        if (au.get("orcid") or "").endswith(orcid):
            out.append(self_name)
        else:
            out.append(short_name(au.get("display_name") or a.get("raw_author_name") or "?"))
    return out
