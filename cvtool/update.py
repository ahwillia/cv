"""Fetch new publications and grants and propose changes to data/*.yaml.

    uv run python -m cvtool.update                 # apply changes, write build/update-report.md
    uv run python -m cvtool.update --dry-run       # report only
    uv run python -m cvtool.update --only grants   # one section

Rejecting a proposal: delete the entry in the PR before merging. Entries listed in
data/pending.yaml that are missing from publications.yaml on the next run are
moved to data/ignored.yaml so they are not proposed again.
"""

import argparse
import sys
from pathlib import Path

from ruamel.yaml.comments import CommentedSeq

from . import grants, pubs, yamlio
from .sources import dblp, nih, openalex

ROOT = yamlio.ROOT
DATA = yamlio.DATA
PUBS = DATA / "publications.yaml"
IGNORED = DATA / "ignored.yaml"
PENDING = DATA / "pending.yaml"
GRANTS = DATA / "grants.yaml"

IGNORED_HEADER = """\
# Works the updater should never propose: {title, dois: [...], reason}.
# Filled automatically when you delete a proposed entry from an update PR;
# you can also add entries by hand.
"""
GRANTS_HEADER = """\
# Grants, newest first. Entries with `source: nih` are kept in sync with
# NIH RePORTER (end date, amount); add other funders by hand without `source`.
#   role:    PI | Contact PI | MPI | Co-I | ...
#   contact: contact PI when you are not; with: other PIs.
#   start/end: "YYYY-MM". amount: total awarded to date (USD).
#   detail:  optional Typst markup replacing the generated role line.
"""
PENDING_HEADER = "# Managed by cvtool.update: entries proposed in the last update PR.\n"


KIND_LABEL = {"journal": "Journal", "conference": "Conference", "preprint": "Preprint", "blog": "Blog"}


def fmt(e) -> str:
    when = e.get("status") or e.get("year")
    s = f"**{KIND_LABEL.get(e['type'], e['type'])}.** {', '.join(e['authors'])} ({when}). {e['title']}. *{e['venue']}*"
    if e.get("details"):
        s += f". {e['details']}"
    if e.get("url"):
        s += f". [paper]({e['url']})"
    if e.get("doi"):
        s += f". [doi:{e['doi']}](https://doi.org/{e['doi']})"
    return s


def report(res: pubs.Result, gres: grants.Result) -> str:
    out = ["## CV update", ""]
    out += [f"> ⚠️ {w}" for w in res.warnings] + ([""] if res.warnings else [])
    if gres.new:
        out += [f"### New grants ({len(gres.new)})", "",
                "Found on NIH RePORTER. Delete any you don't want before merging.", ""]
        for g in gres.new:
            out.append(f"- [ ] `{g['id']}`: {g['title']}. {g['agency']}, {g['role']}, "
                       f"{g['start']} – {g['end']}")
        out.append("")
    if gres.changed:
        out += [f"### Grant updates ({len(gres.changed)})", ""]
        out += [f"- `{i}` {k}: {old} → {new}" for i, k, old, new in gres.changed] + [""]
    if res.new:
        out += [f"### New publications ({len(res.new)})", "",
                "Found on OpenAlex/DBLP but not on the CV. **Delete any you don't want before merging** "
                "and they won't be suggested again. Check author lists for equal-contribution `*` "
                "and that the Journal/Conference/Preprint label is right (`type:` in the YAML).", ""]
        out += [f"- [ ] `{e['id']}`: {fmt(e)}" for e in res.new] + [""]
    if res.published:
        out += [f"### Possibly published ({len(res.published)})", "",
                "These CV entries are preprints or in press, but a published version exists. "
                "Not changed automatically; update venue/year by hand if correct.", ""]
        for e, w in res.published:
            link = f", https://doi.org/{w['doi']}" if w["doi"] else ""
            out.append(f"- `{e['id']}` → {w['kind']}: *{w['venue']}* ({w['year']}){link} [{w['source']}]")
        out.append("")
    if res.urls:
        out += [f"### Paper links added ({len(res.urls)})", ""]
        out += [f"- `{e['id']}` → {u}" for e, u in res.urls] + [""]
    if res.dois:
        out += [f"### DOIs filled in ({len(res.dois)})", ""]
        out += [f"- `{e['id']}` → `{d}`" for e, d in res.dois] + [""]
    if res.auto_ignored:
        out += [f"### Added to ignored.yaml ({len(res.auto_ignored)})", "",
                "Proposed last time and removed before merging.", ""]
        out += [f"- {t}" for t in res.auto_ignored] + [""]
    if not (res.new or res.published or res.dois or res.urls or res.auto_ignored or gres.new or gres.changed):
        out.append("No changes.")
    return "\n".join(out)


def absorb_rejections(pub_entries, grant_entries, ignored, res: pubs.Result) -> None:
    """Pending proposals that were deleted from the CV become ignored."""
    pending = yamlio.load(PENDING) or []
    pub_ids = {e["id"] for e in pub_entries}
    grant_ids = {str(e["id"]) for e in grant_entries}
    for p in pending:
        if "grant" in p:
            if p["grant"] in grant_ids:
                continue
            ig = {"grant": p["grant"], "title": p["title"], "reason": "removed from update PR"}
        else:
            if p["id"] in pub_ids:
                continue
            ig = {"title": p["title"], "dois": [p["doi"]] if p.get("doi") else None,
                  "reason": "removed from update PR"}
        ignored.append(ig)
        res.auto_ignored.append(p["title"])


def fetch_all(profile, cfg, venues, warnings: list) -> list[dict]:
    """Normalized works from every configured source. A failing source is
    skipped with a warning: fewer proposals, but nothing wrong is proposed."""
    me = profile["author_name"]
    sources = {
        "OpenAlex": lambda: [n for w in openalex.fetch(profile["orcid"])
                             if (n := openalex.normalize(w, cfg, profile["orcid"], me, venues))],
    }
    if profile.get("dblp_pid"):
        sources["DBLP"] = lambda: dblp.fetch(profile["dblp_pid"], me, cfg["venue_names"])
    works = []
    for name, get in sources.items():
        try:
            got = get()
        except Exception as exc:  # network / API errors
            warnings.append(f"{name} unavailable ({exc}); its results are missing from this run.")
            continue
        print(f"{name}: {len(got)} works", file=sys.stderr)
        works += got
    if not works:
        raise SystemExit("no source returned any works")
    return works


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", type=Path, default=ROOT / "build" / "update-report.md")
    ap.add_argument("--only", choices=["publications", "grants"])
    args = ap.parse_args()

    config = yamlio.load(ROOT / "config.yaml")
    cfg = config["publications"]
    profile = yamlio.load(DATA / "profile.yaml")
    entries = yamlio.load(PUBS)
    grant_entries = yamlio.load(GRANTS) or []
    ignored = list(yamlio.load(IGNORED) or [])

    res, gres = pubs.Result(), grants.Result()
    absorb_rejections(entries, grant_entries, ignored, res)

    if args.only != "grants":
        works = fetch_all(profile, cfg, yamlio.load(DATA / "venues.yaml"), res.warnings)
        found = pubs.reconcile(entries, works, ignored, cfg)
        res.new, res.dois, res.published, res.urls = found.new, found.dois, found.published, found.urls
        pubs.insert_new(entries, res.new)

    if args.only != "publications" and profile.get("nih_profile_id"):
        try:
            found_grants = nih.fetch(int(profile["nih_profile_id"]))
            print(f"NIH RePORTER: {len(found_grants)} projects", file=sys.stderr)
            ignored_grants = {str(i["grant"]) for i in ignored if i.get("grant")}
            if not grant_entries:
                grant_entries = CommentedSeq()
            gres = grants.reconcile(grant_entries, found_grants, config.get("grants", {}), ignored_grants)
        except Exception as exc:  # network / API errors
            res.warnings.append(f"NIH RePORTER unavailable ({exc}); grants not checked.")

    text = report(res, gres)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(text)
    print(text)

    if not args.dry_run:
        yamlio.save(PUBS, entries)
        if gres.new or gres.changed:
            yamlio.save(GRANTS, grant_entries, header=GRANTS_HEADER)
        if res.auto_ignored:
            yamlio.save_state(IGNORED, ignored, IGNORED_HEADER)
        pending = [{"id": e["id"], "title": e["title"], "doi": e.get("doi")} for e in res.new]
        pending += [{"grant": g["id"], "title": g["title"]} for g in gres.new]
        yamlio.save_state(PENDING, pending, PENDING_HEADER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
