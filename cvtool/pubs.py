"""Reconcile data/publications.yaml against works found online.

Produces three kinds of proposals:
  new        works not on the CV (added to publications.yaml)
  doi        missing DOIs for existing entries (filled in)
  published  preprints / in-press entries that now have a published version
             (reported only; venue formatting is left to you)
"""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from . import yamlio
from .sources import openalex as oa

STOPWORDS = {"a", "an", "the", "on", "of", "in", "for", "with", "and", "to", "from", "via"}


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()


@dataclass
class Paper:
    """One paper, possibly with several OpenAlex records (preprint, VOR, versions)."""
    versions: list[dict] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.best()["title"]

    @property
    def dois(self) -> set[str]:
        return {d for w in self.versions if (d := oa.doi_of(w))}

    def published(self) -> list[dict]:
        return [w for w in self.versions if oa.doi_of(w) and not oa.is_preprint_doi(oa.doi_of(w))]

    def preprints(self) -> list[dict]:
        return [w for w in self.versions if oa.is_preprint_doi(oa.doi_of(w))]

    def best(self) -> dict:
        pub = self.published()
        pool = pub or self.versions
        return min(pool, key=lambda w: (w["type"] != "article", -w["publication_year"], len(oa.doi_of(w) or "~" * 99)))


def keep(w: dict, cfg: dict) -> bool:
    if w["type"] in cfg["exclude_types"]:
        return False
    if oa.venue_of(w) in cfg["exclude_venues"]:
        return False
    title = w.get("title") or ""
    return title and not any(re.search(p, title, re.I) for p in cfg["exclude_titles"])


def cluster(works: list[dict], threshold: float) -> list[Paper]:
    papers: list[Paper] = []
    for w in sorted(works, key=lambda w: w["publication_year"]):
        for p in papers:
            if oa.doi_of(w) in p.dois or any(similar(w["title"], v["title"]) >= threshold for v in p.versions):
                p.versions.append(w)
                break
        else:
            papers.append(Paper([w]))
    return papers


def entry_ids(e) -> set[str]:
    ids = set()
    if e.get("doi"):
        ids.add(str(e["doi"]).lower())
    if e.get("arxiv"):
        ids.add(f"10.48550/arxiv.{e['arxiv']}".lower())
    return ids


def match(paper: Paper, entries, threshold: float):
    for e in entries:
        if entry_ids(e) & paper.dois or any(similar(e["title"], v["title"]) >= threshold for v in paper.versions):
            return e
    return None


def is_ignored(paper: Paper, ignored: list, threshold: float) -> bool:
    for ig in ignored or []:
        if {str(d).lower() for d in ig.get("dois", [])} & paper.dois:
            return True
        if ig.get("title") and similar(ig["title"], paper.title) >= threshold:
            return True
    return False


# ---------------------------------------------------------------- new entries

def slug(authors: list[str], year: int, title: str, taken: set[str]) -> str:
    last = norm_title(authors[0].split()[0]).replace(" ", "") if authors else "anon"
    word = next((w for w in norm_title(title).split() if w not in STOPWORDS and len(w) > 3), "paper")
    base = s = f"{last}{year}{word}"
    n = 2
    while s in taken:
        s, n = f"{base}-{n}", n + 1
    return s


def details_of(w: dict) -> str | None:
    doi = oa.doi_of(w)
    if oa.is_preprint_doi(doi):
        return oa.arxiv_id(doi) or doi.split("/", 1)[1]
    b = w.get("biblio") or {}
    vol, issue, first, last = (b.get(k) for k in ("volume", "issue", "first_page", "last_page"))
    if not vol:
        return None
    s = f"{vol}({issue})" if issue else str(vol)
    if first:
        s += f":{first}" + (f"-{last}" if last and last != first else "")
    return s


def new_entry(paper: Paper, orcid: str, self_name: str, taken: set[str]) -> CommentedMap:
    w = paper.best()
    authors = oa.authors_of(w, orcid, self_name)
    title = re.sub(r"\s+", " ", w["title"]).strip()
    e = CommentedMap()
    e["id"] = slug(authors, w["publication_year"], title, taken)
    e["type"] = "preprint" if oa.is_preprint_doi(oa.doi_of(w)) else "article"
    e["authors"] = CommentedSeq(authors)
    e["authors"].fa.set_flow_style()
    e["year"] = w["publication_year"]
    e["title"] = title
    e["venue"] = oa.venue_of(w) or "TODO venue"
    if d := details_of(w):
        e["details"] = d
    if oa.doi_of(w):
        e["doi"] = oa.doi_of(w)
    return e


# ---------------------------------------------------------------- main entry

@dataclass
class Result:
    new: list = field(default_factory=list)          # CommentedMap entries added
    dois: list = field(default_factory=list)         # (entry, doi)
    published: list = field(default_factory=list)    # (entry, work)
    auto_ignored: list = field(default_factory=list)  # titles

    def changed(self) -> bool:
        return bool(self.new or self.dois or self.auto_ignored)


def published_doi_for(entry, paper: Paper) -> str | None:
    """A published DOI from the same year as the CV entry (avoids errata/corrections)."""
    year = entry.get("year")
    if not year:
        return None
    same_year = [w for w in paper.published() if w["publication_year"] == year]
    if not same_year:
        return None
    w = min(same_year, key=lambda w: (w["type"] not in ("article", "conference-paper", "review"), len(oa.doi_of(w))))
    return oa.doi_of(w)


def reconcile(entries, works, ignored, cfg, orcid, self_name) -> Result:
    res = Result()
    thr = cfg["title_match"]
    papers = cluster([w for w in works if keep(w, cfg)], thr)
    taken = {e["id"] for e in entries}

    for p in papers:
        e = match(p, entries, thr)
        if e is None:
            if p.best()["publication_year"] >= cfg["min_year"] and not is_ignored(p, ignored, thr):
                ne = new_entry(p, orcid, self_name, taken)
                taken.add(ne["id"])
                res.new.append(ne)
            continue

        if not e.get("doi"):
            doi = published_doi_for(e, p) if e["type"] == "article" else (
                oa.doi_of(p.preprints()[0]) if e["type"] == "preprint" and p.preprints() else None)
            if doi:
                yamlio.append_field(e, "doi", doi)
                res.dois.append((e, doi))

        if e["type"] == "preprint" or e.get("status"):
            pub = [w for w in p.published() if w["type"] in ("article", "conference-paper", "review")]
            if pub:
                res.published.append((e, max(pub, key=lambda w: w["publication_year"])))

    return res


def insert_new(entries, new: list) -> None:
    """Articles go to the top of the file, preprints to the top of the preprint block."""
    for e in new:
        if e["type"] == "preprint":
            idx = next((i for i, x in enumerate(entries) if x.get("type") == "preprint"), len(entries))
        else:
            idx = 0
        entries.insert(idx, e)
