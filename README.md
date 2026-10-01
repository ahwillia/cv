# cv-maker

CV content lives in `data/*.yaml`; `templates/cv.typ` renders it to PDF.

```sh
uv run python -m cvtool.build          # -> build/cv.pdf
uv run python -m cvtool.build --png    # -> build/page-N.png previews
```

Fields documented as "Typst markup" accept `_italic_` and `*bold*`.
On push to `main`, GitHub Actions rebuilds the PDF and attaches it to the `latest` release.

## Automatic updates

`uv run python -m cvtool.update` pulls works linked to the ORCID iD in
`data/profile.yaml` from [OpenAlex](https://openalex.org), then:

- adds papers not yet on the CV (from `min_year` in `config.yaml` onward),
- fills in missing DOIs (used for matching; not printed),
- flags preprints / in-press entries that now have a published version.

A weekly GitHub Action runs this and opens a PR with a preview PDF.
To reject a proposed paper, delete its entry in the PR and merge; it is then
recorded in `data/ignored.yaml` and not proposed again.
