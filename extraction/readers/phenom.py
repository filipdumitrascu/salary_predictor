"""Phenom careers sites (Thales, Orange...). Config: host, lang (e.g. en_global), path (job page prefix, e.g. global/en)."""

import html

from ..fetch import post_json
from ..geo import countries_in

PAGE = 100


def _type(t: str | None) -> str | None:
    t = (t or "").lower()
    return "part-time" if "part" in t else "contract" if "contract" in t or "temporary" in t else "full-time" if "full" in t else None


def _post(c, body):
    return post_json(f"https://{c['host']}/widgets", {"lang": c["lang"], "deviceType": "desktop", "country": c["path"].split("/")[0], **body})


def list_jobs(c):
    jobs, start, total = [], 0, 1
    while start < total:
        d = _post(c, {"pageName": "search-results", "ddoKey": "refineSearch", "from": start, "size": PAGE, "jobs": True,
                      "keywords": "", "global": True, "selected_fields": {}})["refineSearch"]
        total, page = d["totalHits"], d["data"]["jobs"]
        if not page:
            break
        for j in page:
            locs = j.get("multi_location") or [j.get("cityStateCountry") or j.get("country") or ""]
            jobs.append({
                "source_id": j["jobId"],
                "title": j["title"],
                "url": f"https://{c['host']}/{c['path']}/job/{j['jobId']}",
                "posted_at": j.get("postedDate"),
                "locations": [loc for loc in locs if loc],
                "countries": countries_in(" | ".join([*locs, j.get("country") or ""])),
                "employment_type": _type(j.get("type")),
            })
        start += len(page)
    return jobs


def detail(c, job):
    d = _post(c, {"pageName": "job", "ddoKey": "jobDetail", "jobId": job["source_id"]})["jobDetail"]["data"]["job"]
    return {**job, "description": html.unescape(d.get("description") or "")}  # arrives HTML-escaped
