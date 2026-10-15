# CLAUDE.md

Alex H Williams's academic CV. This file is for agents working in this repo.
Read `README.md` first for what the system does. This file covers how to
change it safely.

## Layout

```
data/*.yaml          all CV content (source of truth). Header comments document fields.
  profile.yaml       name, ORCID, dblp_pid, nih_profile_id, Scholar stats, section notes
  publications.yaml  every paper; type + category decide the section
  venues.yaml        conference keys -> full names (+ regex to map OpenAlex names)
  grants.yaml        grants; `source: nih` entries are synced by the updater
  ignored.yaml       works/grants the updater must never propose (machine + hand edited)
  pending.yaml       ids proposed in the last update PR (machine-managed; see below)
  positions.yaml     employment (entries in a `group` print without gaps) + other appointments
  education.yaml, awards.yaml, teaching.yaml, service.yaml   hand-maintained sections
  talks.yaml         `conference:` and `seminar:` lists of {date: "YYYY-MM", text}; sorted
                     newest first at build time, same-month talks keep file order
templates/cv.typ     Typst template; reads data/*.yaml directly
cvtool/build.py      data -> build/cv.pdf (or --png previews)
cvtool/update.py     updater CLI: fetch sources, reconcile, write data + build/update-report.md
cvtool/pubs.py       cluster records into papers, match to CV entries, propose changes
cvtool/grants.py     NIH grants reconcile
cvtool/yamlio.py     comment-preserving YAML I/O (ruamel)
cvtool/sources/      openalex.py, dblp.py, crossref.py, nih.py
config.yaml          updater filters (min_year, excluded types/venues, title_match, ...)
.github/workflows/   build.yml (PDF -> "latest" release on push to main), update.yml (weekly PR)
```

## Commands

```sh
uv run python -m cvtool.build --png        # render; then LOOK at build/page-N.png
uv run python -m cvtool.update --dry-run   # what the updater would change; must not error
```

`--dry-run` leaves `data/` untouched but still writes `build/update-report.md`.

- Check every template or layout change by rendering PNGs and looking at the
  affected pages.
- For spacing changes, measure rows of ink in the PNG. Eyeballing is not enough.
- After editing `publications.yaml` or `grants.yaml` by script, confirm they
  round-trip: `yamlio.save(p, yamlio.load(p))` must leave the file identical.
  Edit every other data file (talks, positions, awards, ...) as plain text.
  ruamel reformats their nested lists, and the updater never writes them.

## Data editing rules

- **Edit publications.yaml with `cvtool.yamlio`** (ruamel round-trip), or with
  careful text edits. Never load and dump it with PyYAML: that loses comments,
  quoting and flow-style author lists.
- **Adding a field to an existing entry:** use `yamlio.append_field(entry, key, value)`.
  ruamel attaches the blank line or divider comment that follows an entry to its
  last key. A plain `entry[key] = value` puts the new field after that gap.
- **Writing list fields** (`authors`, `alt_titles`, `with`): use a `CommentedSeq`
  with `.fa.set_flow_style()`.
- **ignored.yaml / pending.yaml:** write them with `yamlio.save_state`. ruamel
  crashes when it re-dumps an emptied commented list.
- **Author format:** "Last Initials", e.g. `Williams AH`. The owner is `Williams AH`,
  which the template bolds. Append `*` for equal contribution.
- **Use full initials consistent with the rest of the CV.** DBLP sometimes
  abbreviates (e.g. `Campbell M` vs `Campbell MG`).
- **Journal `details`:** `volume(issue):pages`, full page ranges, ASCII hyphen
  (the template typesets an en dash). eLife and similar journals use
  `volume:article-number`.
- **Conference entries:** no `details`. Set `venue` to a venues.yaml key and
  `url` to the proceedings, OpenReview or PMLR page.
- **In-press papers:** set `status: In Press`, no `year`, and link the preprint
  with `url` + `link_label: preprint`. Leave `doi` empty so the updater can
  fill in the published one.
- **When an in-press paper is published:** replace `status` with `year`, add
  `doi`, and remove `url` and `link_label`.
  - **Volume/pages:** if the owner gives them, enter them as `details`
    (`vol(issue):pages`). The updater never overwrites existing `details`, so
    ask for the issue number if the journal has issues. If the owner gives no
    numbers, leave `details` out; the next update run fills it from Crossref.
  - **Unverifiable DOI:** if a DOI the owner gives doesn't resolve
    (`doi.org/api/handles/<doi>` not 200), tell them before committing.
    New DOIs can take a few days to register.
  - **Order:** the template sorts by year only. Within a year, file order
    decides. The updater inserts new papers at the top of the file (preprints at
    the top of the preprint block), so file order drifts. That's harmless across
    years; only move an entry when its order *within its year* matters. Keep its `id`.
- **Retyping a preprint as a conference paper** (in the data or in an update PR):
  set `type: conference` and `venue: <venues.yaml key>`. Delete `category`
  and `details`. Set `url` to the proceedings page, or keep the arXiv link with
  `link_label: preprint` plus `status: In Press` if the proceedings aren't out
  yet. Keep `arxiv`/`doi` (they help matching). Add any differing proceedings
  title to `alt_titles`. Keep the `id`.
- **Venue names:** use the journal's official name and spelling (e.g.
  *Nature Human Behaviour*, *Current Opinion in Neurobiology*).
- **Same work under several titles** (e.g. arXiv vs proceedings): put the other
  titles in `alt_titles` so the updater matches them instead of proposing
  duplicates.
- **Removing a paper or grant for good:** delete the entry AND add it to
  `ignored.yaml` (title + dois, or `grant: <id>`) with a reason. Otherwise the
  next weekly run proposes it again. Only deletions made inside an update PR
  are recorded automatically.

## Updater behaviour and gotchas

- **ORCID** (0000-0001-5853-103X) has no public works. OpenAlex is queried
  *by ORCID* instead.
- **DBLP:** the dblp.org REST API sits behind a bot challenge. Use
  `sparql.dblp.org` and do not try to bypass the challenge. Owner pid: `126/4222`.
  DBLP wrongly credits the NeurIPS 2024 VCL paper to a homonym, pid `335/3308`;
  it still matches by title.
- **NIH RePORTER:** search by PI profile ID 15664111, never by name. Name search
  returns an unrelated "Alex N Williamson". F-series fellowships are excluded
  (already listed under Awards).
- **Crossref** rate-limits (429). The client backs off; keep requests sequential.
- **DOI backfill** only takes a published DOI whose year equals the CV entry's
  year. OpenAlex lists errata and corrections (e.g. Neuron 2015/2022/2023
  corrections) as separate works with the same title.
- **Source failures:** a failing source becomes a warning in the report; the run
  still completes with the other sources.
- **New preprints** default to `category: in-prep`. This is deliberate: never
  label something "under review" without the owner saying so.
- **pending.yaml / ignored.yaml mechanism:** the updater records what it proposed
  in `pending.yaml`. On the next run, any pending id missing from the data is
  moved to `ignored.yaml`, unless it is already ignored.
- **Generated PRs:** the weekly workflow skips its run while a `cv-update/auto`
  PR is open, so it never overwrites the owner's edits on that branch.
- **Never rename the `id` of an entry proposed in an open update PR.**
  pending.yaml tracks proposals by id, so a renamed entry counts as "deleted":
  its title goes to ignored.yaml and it is never proposed again. Changing other
  fields (`type`, `venue`, `category`, ...) is fine.
- **Fixing an entry inside an open update PR:** `git fetch origin cv-update/auto`,
  `git switch cv-update/auto`, edit, commit, push, then `git switch main`.
  Commits made at the owner's request count as owner activity: after that,
  never close and regenerate the PR without asking.
- **"Possibly published" items are only reported, never applied.** Check each
  one; conference abstracts can look like publications. If a venue only
  publishes abstracts, add it to `exclude_venues` in config.yaml (Journal of
  Vision, BMC Neuroscience and CCN are already excluded).

## Working with the owner (preferences learned so far)

- **Pushing:** commit and push straightforward data and template changes
  directly to `main`. The `build.yml` workflow publishes the PDF to the
  `latest` release, which is the link the owner shares.
- **After changing `main`:** if a change makes the open update PR conflict or go
  stale, check that PR for owner activity (comments, reviews, non-bot commits).
  If there is none, close it with an explanatory comment and re-run `update.yml`
  to regenerate it. If there is owner activity, ask first.
- **Verify, don't trust:**
  - Check links resolve. For DOIs use `https://doi.org/api/handles/<doi>`.
  - Check Crossref volume/pages against the CV entry before adding a DOI by hand.
  - Look up acceptance rates and similar figures before stating them.
- **Owner's own edits:** the owner sometimes edits files directly (e.g. the
  `conference_note` wording). Keep those edits and match their style.
- **Ask, don't guess:** for anything that would misstate the record, ask the
  owner. Examples: a talk dated in the future, an unclear review status, or a
  grant missing its role. A grant with years only is fine (`start: "2025"`);
  don't ask for months.
- **Awards vs Grants:** prizes and personal fellowships go in awards.yaml
  (McKnight, F32 NRSA, DOE CSGF). Research funding goes in grants.yaml.
- **Layout:** the owner cares about it (symmetric heading spacing, notes tucked
  under headings in gray italics, no orphaned headings). Headings are `sticky`
  blocks; keep it that way.
- **`gh` CLI:** not on PATH. A copy lives at
  `~/claude-chats/2026/loo-cv-nemos/tools/gh_2.96.0_macOS_arm64/bin/gh`,
  authenticated as `ahwillia`. If it's missing, ask the owner to install `gh`
  (e.g. `brew install gh`).

## Typst notes

Typst has no `??` operator. Use `dict.at(key, default: ...)`; the template
defines `get(d, k)`.
