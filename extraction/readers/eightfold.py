"""Eightfold careers sites (Microsoft, Ericsson, Infineon, Vodafone...). Config: host, domain. 10 jobs per page.
api = "v2" for sites that refuse the newer pcsx API (Netflix)."""

import time
from datetime import datetime, timezone

from ..fetch import get_json
from ..geo import countries_in
from ..normalize import office_days

DETAIL_WORKERS = 1  # Microsoft answers 403 when we fetch details in parallel


def _api(c, path, **params):
    return get_json(f"https://{c['host']}/api/pcsx/{path}", params={"domain": c["domain"], **params})["data"]


def list_jobs(c):
    if c.get("api") == "v2":
        return _list_v2(c)
    jobs, start, total = {}, 0, 1
    while start < total:
        d = _api(c, "search", query="", location="", start=start, sort_by="timestamp")
        total = d["count"]
        if not d["positions"]:
            break
        for p in d["positions"]:
            # standardized form is the same on every tenant: "Hyderabad, TS, IN" (city first, country code last)
            std = p.get("standardizedLocations") or []
            jobs[str(p["id"])] = {
                "source_id": str(p["id"]),
                "title": p["name"],
                "url": f"https://{c['host']}/careers/job/{p['id']}",
                "posted_at": datetime.fromtimestamp(p["postedTs"], timezone.utc) if p.get("postedTs") else None,
                "locations": std or p.get("locations") or [],
                "countries": list(dict.fromkeys(cc for s in std if len(cc := s.split(",")[-1].strip()) == 2)),
            }
        start += len(d["positions"])
    return list(jobs.values())


def _list_v2(c):
    jobs, start, total = {}, 0, 1
    while start < total:
        d = get_json(f"https://{c['host']}/api/apply/v2/jobs", params={"domain": c["domain"], "start": start, "num": 10})
        total = d["count"]
        if not d["positions"]:
            break
        for p in d["positions"]:
            locs = p.get("locations") or [p["location"]]  # "Los Gatos,California,United States of America"
            jobs[str(p["id"])] = {
                "source_id": str(p["id"]),
                "title": p["name"],
                "url": p.get("canonicalPositionUrl") or f"https://{c['host']}/careers/job/{p['id']}",
                "posted_at": datetime.fromtimestamp(p["t_create"], timezone.utc) if p.get("t_create") else None,
                "locations": locs,
                "countries": countries_in(" | ".join(locs)),
                "work_mode": p.get("work_location_option") if p.get("work_location_option") in ("onsite", "hybrid", "remote") else None,
            }
        start += len(d["positions"])
    return list(jobs.values())


def detail(c, job):
    time.sleep(0.5)
    if c.get("api") == "v2":
        d = get_json(f"https://{c['host']}/api/apply/v2/jobs/{job['source_id']}", params={"domain": c["domain"]})
        return {**job, "description": d.get("job_description")}
    d = _api(c, "position_details", position_id=job["source_id"])
    site = " ".join(d.get("efcustomTextWorkSite") or []).lower()  # Microsoft only, e.g. "2 days / week in-office"
    etype = " ".join(d.get("efcustomTextEmploymentType") or []).lower()
    return {
        **job,
        "description": d.get("jobDescription"),
        "office_days": 5 if "fully on-site" in site else office_days(site),
        "employment_type": "part-time" if "part" in etype else "full-time" if "full" in etype else None,
    }
