"""Fetch new publications and propose changes to data/publications.yaml.

    uv run python -m cvtool.update            # apply changes, write build/update-report.md
    uv run python -m cvtool.update --dry-run  # report only

Rejecting a proposal: delete the entry in the PR before merging. Entries listed in
data/pending.yaml that are missing from publications.yaml on the next run are
moved to data/ignored.yaml so they are not proposed again.
"""

import argparse
import sys
from pathlib import Path

from . import pubs, yamlio
from .sources import openalex

ROOT = yamlio.ROOT
DATA = yamlio.DATA
PUBS = DATA / "publications.yaml"
IGNORED = DATA / "ignored.yaml"
PENDING = DATA / "pending.yaml"

IGNORED_HEADER = """\
# Works the updater should never propose: {title, dois: [...], reason}.
# Filled automatically when you delete a proposed entry from an update PR;
# you can also add entries by hand.
"""
PENDING_HEADER = "# Managed by cvtool.update: entries proposed in the last update PR.\n"


def fmt(e) -> str:
    when = e.get("status") or e.get("year")
    s = f"{', '.join(e['authors'])} ({when}). {e['title']}. *{e['venue']}*"
    if e.get("details"):
        s += f". {e['details']}"
    if e.get("doi"):
        s += f". [doi:{e['doi']}](https://doi.org/{e['doi']})"
    return s


def report(res: pubs.Result) -> str:
    out = ["## CV update: publications", ""]
    if res.new:
        out += [f"### New publications ({len(res.new)})", "",
                "Found on OpenAlex but not on the CV. **Delete any you don't want before merging** "
                "and they won't be suggested again. Check author lists for equal-contribution `*` "
                "and venues for preprints that were later published.", ""]
        out += [f"- [ ] `{e['id']}`: {fmt(e)}" for e in res.new] + [""]
    if res.published:
        out += [f"### Possibly published ({len(res.published)})", "",
                "These CV entries are preprints or in press, but a published version exists. "
                "Not changed automatically; update venue/year by hand if correct.", ""]
        for e, w in res.published:
            out.append(f"- `{e['id']}` → *{openalex.venue_of(w)}* ({w['publication_year']}), "
                       f"https://doi.org/{openalex.doi_of(w)}")
        out.append("")
    if res.dois:
        out += [f"### DOIs filled in ({len(res.dois)})", ""]
        out += [f"- `{e['id']}` → `{d}`" for e, d in res.dois] + [""]
    if res.auto_ignored:
        out += [f"### Added to ignored.yaml ({len(res.auto_ignored)})", "",
                "Proposed last time and removed before merging.", ""]
        out += [f"- {t}" for t in res.auto_ignored] + [""]
    if len(out) == 2:
        out.append("No changes.")
    return "\n".join(out)


def absorb_rejections(entries, ignored, res: pubs.Result) -> None:
    """Pending proposals that were deleted from the CV become ignored."""
    pending = yamlio.load(PENDING) or []
    present = {e["id"] for e in entries}
    for p in pending:
        if p["id"] not in present:
            ig = {"title": p["title"], "dois": [p["doi"]] if p.get("doi") else None,
                  "reason": "removed from update PR"}
            ignored.append(ig)
            res.auto_ignored.append(p["title"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", type=Path, default=ROOT / "build" / "update-report.md")
    args = ap.parse_args()

    cfg = yamlio.load(ROOT / "config.yaml")["publications"]
    profile = yamlio.load(DATA / "profile.yaml")
    entries = yamlio.load(PUBS)
    ignored = list(yamlio.load(IGNORED) or [])

    works = openalex.fetch(profile["orcid"])
    print(f"OpenAlex: {len(works)} works for ORCID {profile['orcid']}", file=sys.stderr)

    res = pubs.Result()
    absorb_rejections(entries, ignored, res)
    found = pubs.reconcile(entries, works, ignored, cfg, profile["orcid"], profile["author_name"])
    res.new, res.dois, res.published = found.new, found.dois, found.published
    pubs.insert_new(entries, res.new)

    text = report(res)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(text)
    print(text)

    if not args.dry_run:
        yamlio.save(PUBS, entries)
        if res.auto_ignored:
            yamlio.save_state(IGNORED, ignored, IGNORED_HEADER)
        pending = [{"id": e["id"], "title": e["title"], "doi": e.get("doi")} for e in res.new]
        yamlio.save_state(PENDING, pending, PENDING_HEADER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
