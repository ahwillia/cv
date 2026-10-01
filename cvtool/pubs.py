"""Reconcile data/publications.yaml against works found online.

Sources (cvtool/sources/*) return normalized works:
    {source, key, title, year, kind, venue, details, doi, authors, url}
with kind one of journal | conference | preprint. Conference venues are
data/venues.yaml keys (NeurIPS, ICLR, ...).

Produces three kinds of proposals:
  new        works not on the CV (added to publications.yaml)
  doi        missing DOIs for existing entries (filled in)
  url        paper links for conference entries (filled in; an arXiv link is
             replaced once a proceedings link exists)
  published  preprints / in-press entries that now have a published version
             (reported only; venue formatting is left to you)
"""

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from . import yamlio
from .sources.openalex import is_preprint_doi

STOPWORDS = {"a", "an", "the", "on", "of", "in", "for", "with", "and", "to", "from", "via"}
PUBLISHED = ("journal", "conference")


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()


def _source_rank(w: dict) -> int:
    # DBLP has clean venue names for conferences; OpenAlex has DOIs/pages for journals.
    preferred = "dblp" if w["kind"] == "conference" else "openalex"
    return 0 if w["source"] == preferred else 1


@dataclass
class Paper:
    """One paper, possibly with several records (preprint, published, versions, sources)."""
    versions: list[dict] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.best()["title"]

    @property
    def titles(self) -> list[str]:
        return [w["title"] for w in self.versions]

    @property
    def dois(self) -> set[str]:
        return {w["doi"] for w in self.versions if w["doi"]}

    def published(self) -> list[dict]:
        return [w for w in self.versions if w["kind"] in PUBLISHED]

    def preprints(self) -> list[dict]:
        return [w for w in self.versions if w["kind"] == "preprint"]

    def best(self) -> dict:
        return min(self.versions, key=lambda w: (
            w["kind"] not in PUBLISHED, not w["venue"], _source_rank(w),
            -w["year"], len(w["doi"] or "~" * 99)))


def cluster(works: list[dict], threshold: float) -> list[Paper]:
    papers: list[Paper] = []
    for w in sorted(works, key=lambda w: w["year"]):
        for p in papers:
            if (w["doi"] and w["doi"] in p.dois) or any(similar(w["title"], t) >= threshold for t in p.titles):
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


def entry_titles(e) -> list[str]:
    return [e["title"], *e.get("alt_titles", [])]


def match(paper: Paper, entries, threshold: float):
    for e in entries:
        if entry_ids(e) & paper.dois or any(
                similar(a, b) >= threshold for a in entry_titles(e) for b in paper.titles):
            return e
    return None


def is_ignored(paper: Paper, ignored: list, threshold: float) -> bool:
    for ig in ignored or []:
        if ig.get("grant"):
            continue
        if {str(d).lower() for d in ig.get("dois") or []} & paper.dois:
            return True
        if ig.get("title") and any(similar(ig["title"], t) >= threshold for t in paper.titles):
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


def new_entry(paper: Paper, taken: set[str]) -> CommentedMap:
    w = paper.best()
    # Prefer a record that has a DOI for the identifier, if one exists of the same kind.
    doi = w["doi"] or next((v["doi"] for v in paper.versions if v["doi"] and v["kind"] == w["kind"]), None)
    e = CommentedMap()
    e["id"] = slug(w["authors"], w["year"], w["title"], taken)
    e["type"] = w["kind"]
    e["authors"] = CommentedSeq(w["authors"])
    e["authors"].fa.set_flow_style()
    e["year"] = w["year"]
    e["title"] = w["title"]
    e["venue"] = w["venue"] or "TODO venue"
    if w["details"] and w["kind"] != "conference":
        e["details"] = w["details"]
    if url := conference_url(paper):
        e["url"] = url
    if doi:
        e["doi"] = doi
    if w["kind"] == "preprint":
        e["category"] = "in-prep"  # conservative default; the PR asks you to check it
    return e


def conference_url(paper: Paper) -> str | None:
    return next((w["url"] for w in paper.versions if w["kind"] == "conference" and w.get("url")), None)


def is_arxiv(url) -> bool:
    return "arxiv.org" in str(url or "")


# ---------------------------------------------------------------- main entry

@dataclass
class Result:
    new: list = field(default_factory=list)           # CommentedMap entries added
    dois: list = field(default_factory=list)          # (entry, doi)
    urls: list = field(default_factory=list)          # (entry, url)
    details: list = field(default_factory=list)       # (entry, volume/issue/pages)
    published: list = field(default_factory=list)     # (entry, work)
    auto_ignored: list = field(default_factory=list)  # titles
    warnings: list = field(default_factory=list)

    def changed(self) -> bool:
        return bool(self.new or self.dois or self.urls or self.details or self.auto_ignored)


def published_doi_for(entry, paper: Paper) -> str | None:
    """A published DOI from the same year as the CV entry (avoids errata/corrections)."""
    year = entry.get("year")
    same_year = [w for w in paper.published()
                 if w["year"] == year and w["doi"] and not is_preprint_doi(w["doi"])]
    if not same_year:
        return None
    return min(same_year, key=lambda w: len(w["doi"]))["doi"]


def reconcile(entries, works, ignored, cfg) -> Result:
    res = Result()
    thr = cfg["title_match"]
    taken = {e["id"] for e in entries}

    for p in cluster(works, thr):
        e = match(p, entries, thr)
        if e is None:
            if p.best()["year"] >= cfg["min_year"] and not is_ignored(p, ignored, thr):
                ne = new_entry(p, taken)
                taken.add(ne["id"])
                res.new.append(ne)
            continue

        if not e.get("doi"):
            if e["type"] in PUBLISHED:
                doi = published_doi_for(e, p)
            elif e["type"] == "preprint":
                doi = next((w["doi"] for w in p.preprints() if w["doi"]), None)
            else:
                doi = None
            if doi:
                yamlio.append_field(e, "doi", doi)
                res.dois.append((e, doi))

        if e["type"] == "conference" and (not e.get("url") or is_arxiv(e["url"])):
            if url := conference_url(p):
                if "url" in e:
                    e["url"] = url
                else:
                    yamlio.append_field(e, "url", url)
                if e.get("link_label") == "preprint":  # now the proceedings version
                    del e["link_label"]
                res.urls.append((e, url))

        if e["type"] == "preprint" or e.get("status"):
            pub = p.published()
            if pub:
                res.published.append((e, max(pub, key=lambda w: (w["year"], -_source_rank(w)))))

    return res


def insert_new(entries, new: list) -> None:
    """Published papers go to the top of the file, preprints to the top of the preprint block."""
    for e in new:
        if e["type"] == "preprint":
            idx = next((i for i, x in enumerate(entries) if x.get("type") == "preprint"), len(entries))
        else:
            idx = 0
        entries.insert(idx, e)
