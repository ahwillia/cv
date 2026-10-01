"""Volume / issue / pages for a DOI from Crossref (https://api.crossref.org).

Formats journal details in the CV's standard form: "volume(issue):pages", with
full page ranges ("809-821", not "809-21") and article numbers ("14:RP108943")
when there are no pages.
"""

import json
import re
import time
import urllib.parse
import urllib.request

API = "https://api.crossref.org/works/"
USER_AGENT = "cv-maker/0.1 (https://github.com/ahwillia/cv)"


def _get(doi: str) -> dict:
    url = API + urllib.parse.quote(doi)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)["message"]
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 3:  # rate limited: back off and retry
                raise
            time.sleep(10 * (attempt + 1))


def expand_range(pages: str) -> str:
    """'2905-17' -> '2905-2917', 'E2645-54' -> 'E2645-E2654'; leaves '2967-2980.e11' alone."""
    m = re.fullmatch(r"([A-Za-z]*)(\d+)\s*[-–]\s*([A-Za-z]*)(\d+)(.*)", pages.strip())
    if not m:
        return pages.strip()
    p1, a, p2, b, rest = m.groups()
    if len(b) < len(a):
        b = a[: len(a) - len(b)] + b
    return f"{p1}{a}-{p2 or p1}{b}{rest}"


def fmt(volume, issue, pages) -> str | None:
    if not volume:
        return None
    s = f"{volume}({issue})" if issue else str(volume)
    return f"{s}:{expand_range(pages)}" if pages else s


def details(doi: str) -> str | None:
    """Standard-form details for `doi`, or None if Crossref lacks a volume."""
    m = _get(doi)
    return fmt(m.get("volume"), m.get("issue"), m.get("page") or m.get("article-number"))


def parse(details: str) -> tuple[str | None, str | None, str | None]:
    """Split existing CV details ('218(18): 2905-17', '70: 193-205') into parts."""
    m = re.fullmatch(r"\s*([^():\s]+)\s*(?:\(([^)]*)\))?\s*(?::\s*(.+))?", str(details))
    return m.groups() if m else (None, None, None)
