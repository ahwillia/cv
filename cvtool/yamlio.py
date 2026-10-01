"""Comment-preserving YAML load/save for the data files."""

import io
import re
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=2, offset=0)
    return y


def load(path: Path):
    if not path.exists():
        return None
    return _yaml().load(path.read_text())


def append_field(m, key, value) -> None:
    """Add `key` to the end of mapping `m`, keeping trailing blank lines/comments
    (which ruamel attaches to the previous last key) after the new field."""
    last = next(reversed(m), None) if m else None
    tok = m.ca.items.pop(last, None) if last is not None else None
    m[key] = value
    if tok:
        m.ca.items[key] = tok


def save(path: Path, data, header: str | None = None) -> None:
    buf = io.StringIO()
    _yaml().dump(data, buf)
    text = buf.getvalue()
    if header and not text.startswith("#"):
        text = header.rstrip() + "\n\n" + text
    # Keep one blank line between top-level list entries.
    text = re.sub(r"(?<!\n)\n- id:", "\n\n- id:", text)
    path.write_text(text)


def save_state(path: Path, items: list, header: str) -> None:
    """Write a machine-managed list file: fixed comment header + plain YAML."""
    plain = [{k: v for k, v in dict(i).items() if v is not None} for i in items]
    body = "[]\n"
    if plain:
        buf = io.StringIO()
        _yaml().dump(plain, buf)
        body = re.sub(r"\n(?=- )", "\n\n", buf.getvalue()).lstrip("\n")
    path.write_text(header.rstrip() + "\n\n" + body)
