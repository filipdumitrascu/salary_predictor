"""Radancy (TalentBrew) careers sites (Synopsys, ING...). Config: base (site root incl. language, e.g. https://careers.ing.com/en).
The list comes as JSON-wrapped HTML; each job page carries schema.org JobPosting data (JSON-LD)."""

import html
import re
from urllib.parse import urljoin

from ..fetch import request
from .jsonld import apply_posting, job_posting

PAGE = 100
CARD = re.compile(r'<a[^>]+href="(/[^"]*job/[^"]+)"[^>]*data-job-id="(\d+)"[^>]*>(.*?)</a>', re.S)


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def list_jobs(c):
    jobs, page, pages = {}, 1, 1
    while page <= pages:
        params = {"CurrentPage": page, "RecordsPerPage": PAGE, "SearchResultsModuleName": "Search Results",
                  "SearchFiltersModuleName": "Search Filters", "SearchType": 5, "IsPagination": "True"}
        r = request("GET", f"{c['base']}/search-jobs/results", params=params, headers={"X-Requested-With": "XMLHttpRequest"}).json()["results"]
        pages = int((re.search(r'data-total-pages="(\d+)"', r) or [0, 1])[1])
        for link, jid, card in CARD.findall(r):
            title = re.search(r"<h2[^>]*>(.*?)</h2>", card, re.S)
            loc = re.search(r'job-location[^>]*>(.*?)<', card, re.S)
            jobs.setdefault(jid, {
                "source_id": jid,
                "title": _text(title.group(1) if title else card),
                "url": urljoin(c["base"] + "/", link),
                "locations": [_text(loc.group(1))] if loc else [],
            })
        page += 1
    return list(jobs.values())


def detail(c, job):
    return apply_posting(job, job_posting(request("GET", job["url"]).text))
