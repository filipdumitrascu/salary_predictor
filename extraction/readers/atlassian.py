"""Atlassian careers: the all-jobs page embeds every job as JSON; each job's page has the description."""

import json
import re

from ..fetch import request
from ..geo import countries_in

BASE = "https://www.atlassian.com/company/careers"
JOB = re.compile(r'"fields":(\{"applyUrl".*?"type":(?:null|"[^"]*")\})')


def list_jobs(c):
    jobs = {}
    for raw in JOB.findall(request("GET", f"{BASE}/all-jobs").text):
        j = json.loads(raw)
        # "Seattle - United States -   Seattle, Washington  United States", "Remote - UK - Remote"
        locs = [re.sub(r"\s+", " ", loc).strip() for loc in j["locations"] or []]
        jobs[j["id"]] = {
            "source_id": j["id"],
            "title": j["title"],
            "url": f"{BASE}/details/{j['id']}",
            "locations": locs,
            "countries": countries_in(" | ".join(locs)),
            "work_mode": "remote" if locs and all(loc.lower().startswith("remote") for loc in locs) else None,
        }
    return list(jobs.values())


def detail(c, job):
    page = request("GET", job["url"]).text
    start = page.find("<p><b>")  # the description starts with its first bold heading ("About the role")
    return {**job, "description": page[start:start + 15000] if start >= 0 else ""}
