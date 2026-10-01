"""Reconcile data/grants.yaml against NIH RePORTER.

  new      NIH projects not in grants.yaml (added)
  changed  end date or total awarded changed for an NIH-sourced entry (updated)

Hand-written entries (no `source: nih`) are never modified.
"""

import re
from dataclasses import dataclass, field

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from . import yamlio

TRACKED = ("end", "amount")


@dataclass
class Result:
    new: list = field(default_factory=list)      # CommentedMap entries
    changed: list = field(default_factory=list)  # (id, field, old, new)


def to_entry(g: dict) -> CommentedMap:
    e = CommentedMap()
    for k in ("id", "title", "agency", "mechanism", "role", "contact", "with", "start", "end", "amount"):
        v = g.get(k)
        if v in (None, []):
            continue
        if k == "with":
            v = CommentedSeq(v)
            v.fa.set_flow_style()
        e[k] = v
    e["source"] = "nih"
    return e


def reconcile(entries, found: list[dict], cfg: dict, ignored_ids: set[str]) -> Result:
    res = Result()
    by_id = {str(e["id"]): e for e in entries}
    skip = re.compile(cfg.get("exclude_mechanisms", "^$"))
    pos = 0  # `found` is newest first; keep that order at the top of the file
    for g in found:
        e = by_id.get(g["id"])
        if e is None:
            if not skip.search(g["mechanism"]) and g["id"] not in ignored_ids:
                ne = to_entry(g)
                entries.insert(pos, ne)
                pos += 1
                res.new.append(ne)
            continue
        if e.get("source") != "nih":
            continue
        for k in TRACKED:
            if g.get(k) is not None and str(e.get(k)) != str(g[k]):
                res.changed.append((g["id"], k, e.get(k), g[k]))
                if k in e:
                    e[k] = g[k]
                else:
                    yamlio.append_field(e, k, g[k])
    return res
