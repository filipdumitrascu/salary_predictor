"""Lever public postings API (Spotify...): every job with its description in one request.
Config: board; eu = true for boards hosted on api.eu.lever.co."""

from datetime import datetime, timezone

from ..fetch import get_json
from ..geo import countries_in

MODE = {"onsite": "onsite", "hybrid": "hybrid", "remote": "remote"}


def list_jobs(c):
    host = "api.eu.lever.co" if c.get("eu") else "api.lever.co"
    jobs = []
    for j in get_json(f"https://{host}/v0/postings/{c['board']}", params={"mode": "json"}):
        locs = j["categories"].get("allLocations") or [j["categories"].get("location")]
        locs = [loc for loc in locs if loc]
        jobs.append({
            "source_id": j["id"],
            "title": j["text"],
            "url": j["hostedUrl"],
            "description": " ".join(filter(None, [j.get("descriptionPlain"), *(l.get("content", "") for l in j.get("lists", [])), j.get("additionalPlain")])),
            "posted_at": datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc) if j.get("createdAt") else None,
            "locations": locs,
            "countries": countries_in(" | ".join(locs)) or ([j["country"]] if j.get("country") else []),
            "work_mode": MODE.get(j.get("workplaceType")),
        })
    return jobs
