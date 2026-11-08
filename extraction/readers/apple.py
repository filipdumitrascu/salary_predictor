"""Apple jobs. The search API (it needs a CSRF token from the site first) lists the jobs, 20 per page,
with only a short summary. The full ad, including the pay range ("At Apple, base pay is one part of our
total compensation package... between $X and $Y"), is in the job's own page: the page carries the job
as JSON inside a script (JSON.parse("...")), so detail() reads that page and keeps every text in it.
Config: countries (optional list of ISO-2 codes, e.g. ["US"]): only those jobs get their page read."""

import json
import re

from ..fetch import request, session
from ..geo import countries_in

BASE = "https://jobs.apple.com"
DETAIL_WORKERS = 2
EMBEDDED = re.compile(r'JSON\.parse\(("(?:[^"\\]|\\.)*")\)', re.S)  # a JS string literal holding JSON


def list_jobs(c):
    token = request("GET", f"{BASE}/api/v1/CSRFToken").headers["x-apple-csrf-token"]
    headers = {"x-apple-csrf-token": token, "origin": BASE, "referer": f"{BASE}/en-us/search"}
    jobs, page, total = {}, 1, 1
    while len(jobs) < total:
        d = request("POST", f"{BASE}/api/v1/search", headers=headers,
                    json={"query": "", "filters": {}, "page": page, "locale": "en-us", "sort": "newest",
                          "format": {"longDate": "MMMM D, YYYY", "mediumDate": "MMM D, YYYY"}}).json()["res"]  # 0 results without "format"
        total = d["totalRecords"]
        if not d["searchResults"]:
            break
        for j in d["searchResults"]:
            locs = [", ".join(filter(None, [l.get("city"), l.get("stateProvince"), l.get("countryName")])) or l["name"]
                    for l in j["locations"]]
            jobs[j["positionId"]] = {
                "source_id": j["positionId"],
                "title": j["postingTitle"],
                "url": f"{BASE}/en-us/details/{j['positionId']}/{j.get('transformedPostingTitle', '')}",
                "description": j.get("jobSummary"),
                "posted_at": j.get("postDateInGMT"),
                "locations": locs,
                "countries": countries_in(" | ".join(l["countryName"] for l in j["locations"])),
                "employment_type": "part-time" if "part-time" in j["postingTitle"].lower() else None,
            }
        page += 1
    session.cookies.clear()  # the CSRF cookie belongs to this listing only
    wanted = set(c.get("countries") or [])
    return [j for j in jobs.values() if not wanted or wanted & set(j["countries"])]


def _texts(value, out):
    """Every text of 40+ characters inside a JSON value (the ad's sections), in order."""
    if isinstance(value, dict):
        for v in value.values():
            _texts(v, out)
    elif isinstance(value, list):
        for v in value:
            _texts(v, out)
    elif isinstance(value, str) and len(value) >= 40 and " " in value:
        out.append(value)
    return out


def page_text(page: str) -> str:
    """The ad's text from an Apple job page: every text in its embedded JSON, without repeats."""
    texts = []
    for literal in EMBEDDED.findall(page):
        try:
            _texts(json.loads(json.loads(literal)), texts)
        except ValueError:
            continue
    if not texts:  # no JSON.parse(...) found: fall back to the page with its escaped quotes undone
        from ..normalize import html_to_text
        return html_to_text(page.replace('\\"', '"').replace("\\n", "\n"))
    return "\n\n".join(dict.fromkeys(texts))


def detail(c, job):
    text = page_text(request("GET", job["url"]).text)
    if not text:
        raise RuntimeError("no job data in the page (page format changed?)")
    return {**job, "description": text}
