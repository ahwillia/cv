# cv-maker

Alex H Williams's academic CV, generated from structured data and kept up to
date automatically.

**Latest PDF:** https://github.com/ahwillia/cv/releases/download/latest/cv.pdf
(rebuilt on every push to `main`).

- `data/*.yaml`: all CV content. Edit these by hand; each file's header comment
  documents its fields.
- `templates/cv.typ`: the [Typst](https://typst.app) template that renders the PDF.
- `cvtool/`: the build script and the updater that proposes new publications and grants.

## Build

```sh
uv run python -m cvtool.build          # -> build/cv.pdf
uv run python -m cvtool.build --png    # -> build/page-N.png previews
```

Typst ships with the `typst` Python package, so `uv` is the only requirement.
Locally the CV uses Palatino (macOS); CI downloads TeX Gyre Pagella, a free
font with the same letter widths.

## Content

- **Publications** (`data/publications.yaml`) are grouped by `type`:
  - `journal`: Peer-Reviewed Publications > Journal Articles.
  - `conference`: Peer-Reviewed Publications > Conference Proceedings. `venue`
    is a key from `data/venues.yaml`, printed as "*Full Name* (KEY)", with an
    explanatory note from `conference_note` in `profile.yaml`.
  - `preprint`: Other Manuscripts. `category` picks the subsection:
    `under-review`, `report` (Technical Reports, with `report_note`) or
    `in-prep` (In Preparation).
  - `blog`: Blog Posts. The section is hidden when it has no entries.
- **Links:** each citation ends with a `[paper]` link. It uses `url` if set,
  otherwise the arXiv abstract page, otherwise the DOI. Set `link_label` to
  change the text, e.g. `[preprint]` for in-press papers.
- **Forthcoming papers:** set `status: In Press` instead of `year`.
- **Grants** (`data/grants.yaml`): entries with `source: nih` are synced from
  NIH RePORTER; add other funders by hand.
- **Google Scholar** citation count and h-index are updated by hand in
  `data/profile.yaml`, because Scholar has no API.
- **Everything else** is edited by hand: positions, education, awards,
  teaching, talks (`data/talks.yaml`: `{date: "YYYY-MM", text}` under
  `conference:` or `seminar:`), and service.
- Fields documented as "Typst markup" accept `_italic_` and `*bold*`.

## Automatic updates

`uv run python -m cvtool.update` (add `--dry-run` to only report) checks:

| Source | Used for |
|---|---|
| [OpenAlex](https://openalex.org) (by ORCID iD) | journal papers, preprints, DOIs |
| [DBLP](https://dblp.org) (SPARQL, by `dblp_pid`) | conference papers, venue keys, proceedings links |
| [Crossref](https://www.crossref.org) | volume/issue/pages for journal entries with a DOI |
| [NIH RePORTER](https://reporter.nih.gov) (by `nih_profile_id`) | NIH grants, end dates |

It then:

- adds papers and grants not yet on the CV (papers from `min_year` in `config.yaml` onward),
- fills in missing DOIs, conference links and journal volume/pages,
- flags preprints and in-press papers that now have a published version (report only).

A weekly GitHub Action (Mondays 13:00 UTC, or run by hand from the Actions tab)
runs the updater and opens a "CV update" PR with a preview PDF.

**Rejecting a proposal:** delete its entry in the PR, then merge. The next run
records it in `data/ignored.yaml`, so it is not proposed again. To drop
something that is already on the CV, delete it and add it to `ignored.yaml`
yourself. **Don't rename the `id` of a proposed entry inside the PR:** the next
run would treat it as rejected.
