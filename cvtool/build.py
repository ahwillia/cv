"""Render data/*.yaml into build/cv.pdf via the Typst template."""

import argparse
from pathlib import Path

import typst

ROOT = Path(__file__).resolve().parent.parent


def build(out: Path, fmt: str = "pdf") -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fonts = [str(p) for p in [ROOT / "fonts"] if p.is_dir()]
    typst.compile(
        str(ROOT / "templates" / "cv.typ"),
        output=str(out),
        root=str(ROOT),
        font_paths=fonts,
        format=fmt,
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "cv.pdf")
    ap.add_argument("--png", action="store_true", help="render PNG pages instead (for previews)")
    args = ap.parse_args()
    if args.png:
        out = args.output.with_name("page-{p}.png")
        build(out, "png")
    else:
        out = build(args.output)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
