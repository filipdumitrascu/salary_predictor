"""Careers sites whose job pages carry schema.org JobPosting data (JSON-LD), with numbered list pages (Luxoft).
Config: list_url (with {page}, e.g. https://career.luxoft.com/jobs?page={page}), link (regex for job URLs)."""

import json
import re
from urllib.parse import urljoin

import requests

from ..fetch import request
from ..geo import countries_in


def job_posting(page: str) -> dict:
    """The page's schema.org JobPosting as a dict ({} if none)."""
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and "JobPosting" in str(data.get("@type")):
            return data
    return {}


def apply_posting(job: dict, posting: dict) -> dict:
    """The job with title, description, date and locations filled from its JobPosting."""
    places = posting.get("jobLocation") or []
    places = places if isinstance(places, list) else [places]
    locs = [", ".join(filter(None, [(p.get("address") or {}).get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]))
            for p in places] or job.get("locations") or []
    locs = [loc for loc in locs if loc]
    remote = "TELECOMMUTE" in str(posting.get("jobLocationType"))
    if not locs:  # remote jobs name only the countries they hire in: {"@type": "Country", "name": "India"}
        allowed = posting.get("applicantLocationRequirements") or []
        locs = [a.get("name") for a in (allowed if isinstance(allowed, list) else [allowed]) if a.get("name")]
    codes = [c for p in places if len(c := str((p.get("address") or {}).get("addressCountry") or "")) == 2 and c.isupper()]
    text = " ".join(str(posting.get(k) or "") for k in ("description", "responsibilities", "experienceRequirements"))
    return {**job, "title": posting.get("title") or job["title"], "locations": locs, "countries": list(dict.fromkeys(codes)) or countries_in(" | ".join(locs)),
            "description": text, "posted_at": posting.get("datePosted"), "work_mode": "remote" if remote else job.get("work_mode")}


def list_jobs(c):
    jobs, page = {}, 1
    while page <= 500:
        url = c["list_url"].format(page=page)
        try:
            text = request("GET", url).text
        except requests.HTTPError as e:
            if e.response.status_code == 404:  # some sites answer 404 past the last page
                break
            raise
        new = [u for u in dict.fromkeys(urljoin(url, u) for u in re.findall(r'href="(%s)"' % c["link"], text)) if u not in jobs]
        if not new:  # past the last page
            break
        jobs.update((u, {"source_id": u.rstrip("/").rsplit("/", 1)[-1], "title": "", "url": u}) for u in new)
        page += 1
    return list(jobs.values())


def detail(c, job):
    return apply_posting(job, job_posting(request("GET", job["url"]).text))
