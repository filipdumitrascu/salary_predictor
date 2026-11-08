"""Greenhouse public job board API: every job with its description in one request. Config: board."""

import html
import re

from ..fetch import get_json
from ..geo import countries_in

# Some companies write the work mode instead of a place (Cloudflare); the cities are then in "offices".
MODE_LABELS = {"hybrid": "hybrid", "distributed": "remote", "in-office": "onsite"}


def _parts(job):
    """One location field can hold several: "San Francisco, CA | New York City, NY", "Austin, TX; Remote"."""
    return [p.strip() for p in re.split(r"[;|]", job["location"]["name"]) if p.strip()]


def _places(job):
    places = [p for p in _parts(job) if p.lower() not in MODE_LABELS]
    return places or [o["name"] for o in job.get("offices") or []]


def _work_mode(job):
    modes = {MODE_LABELS[p.lower()] for p in _parts(job) if p.lower() in MODE_LABELS}
    return modes.pop() if len(modes) == 1 else None


def list_jobs(c):
    d = get_json(f"https://boards-api.greenhouse.io/v1/boards/{c['board']}/jobs", params={"content": "true"})
    return [
        {
            "source_id": str(j["id"]),
            "title": j["title"],
            "url": j["absolute_url"],
            "description": html.unescape(j.get("content") or ""),  # content arrives HTML-escaped
            "posted_at": j.get("first_published"),  # "updated_at" is not a posting date
            "locations": _places(j),
            "countries": countries_in(" | ".join(_places(j))),
            "work_mode": _work_mode(j),
        }
        for j in d["jobs"]
    ]
