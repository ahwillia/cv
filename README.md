# cv-maker

CV content lives in `data/*.yaml`; `templates/cv.typ` renders it to PDF.

```sh
uv run python -m cvtool.build          # -> build/cv.pdf
uv run python -m cvtool.build --png    # -> build/page-N.png previews
```

Fields documented as "Typst markup" accept `_italic_` and `*bold*`.
On push to `main`, GitHub Actions rebuilds the PDF and attaches it to the `latest` release.
