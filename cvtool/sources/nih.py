"""Fetch NIH awards for a PI from NIH RePORTER (https://api.reporter.nih.gov).

Searches by RePORTER PI profile ID rather than name, so other "A Williams"
investigators are never matched. Each fiscal-year record is collapsed into one
grant per core project number.
"""

import json
import urllib.request
from collections import defaultdict

API = "https://api.reporter.nih.gov/v2/projects/search"
FIELDS = ["ProjectNum", "CoreProjectNum", "ProjectTitle", "FiscalYear", "PrincipalInvestigators",
          "ProjectStartDate", "ProjectEndDate", "AgencyIcAdmin", "ActivityCode", "AwardAmount"]


def _search(profile_id: int) -> list[dict]:
    out, offset = [], 0
    while True:
        body = {"criteria": {"pi_profile_ids": [profile_id]}, "include_fields": FIELDS,
                "offset": offset, "limit": 500}
        req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            page = json.load(r)
        out += page["results"]
        offset += len(page["results"])
        if not page["results"] or offset >= page["meta"]["total"]:
            return out


def _name(pi: dict) -> str:
    return f"{pi['first_name']} {pi['last_name']}".strip()


def fetch(profile_id: int) -> list[dict]:
    """One dict per core project: id, title, agency, mechanism, role, contact, with, start, end, amount."""
    by_core = defaultdict(list)
    for r in _search(profile_id):
        by_core[r["core_project_num"]].append(r)

    grants = []
    for core, recs in by_core.items():
        latest = max(recs, key=lambda r: r["fiscal_year"])
        pis = latest["principal_investigators"]
        me = next(p for p in pis if p["profile_id"] == profile_id)
        others = [p for p in pis if p["profile_id"] != profile_id]
        contact = next((p for p in others if p["is_contact_pi"]), None)
        if not others:
            role = "PI"
        elif me["is_contact_pi"]:
            role = "Contact PI"
        else:
            role = "MPI"
        ic = (latest.get("agency_ic_admin") or {}).get("abbreviation")
        grants.append({
            "id": core,
            "title": latest["project_title"].strip(),
            "agency": f"NIH/{ic}" if ic else "NIH",
            "mechanism": latest["activity_code"],
            "role": role,
            "contact": _name(contact) if contact else None,
            "with": [_name(p) for p in others if p is not contact],
            "start": min(r["project_start_date"] for r in recs)[:7],
            "end": max(r["project_end_date"] for r in recs)[:7],
            "amount": sum(r.get("award_amount") or 0 for r in recs),
        })
    return sorted(grants, key=lambda g: g["start"], reverse=True)
