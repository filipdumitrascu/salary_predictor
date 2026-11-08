"""Google careers. No public API: the job list is embedded as JSON in each results page (20 jobs/page).
Fields are positional arrays, so a Google redesign breaks this reader - the run then fails loudly."""

import json
import re
import time
from datetime import datetime, timezone

from ..fetch import request

URL = "https://www.google.com/about/careers/applications/jobs/results"
DATA = re.compile(r"AF_initDataCallback\(\{key: 'ds:1', hash: '\d+', data:(.*?), sideChannel: \{\}\}\);</script>", re.S)


def _text(field):
    return field[1] if isinstance(field, list) and len(field) > 1 and field[1] else ""


def _job(r):
    slug = re.sub(r"[^a-z0-9]+", "-", r[1].lower()).strip("-")
    locs = r[9] or []
    return {
        "source_id": r[0],
        "title": r[1],
        "url": f"{URL}/{r[0]}-{slug}",
        "description": _text(r[10]) + "<h3>Responsibilities</h3>" + _text(r[3]) + "<h3>Qualifications</h3>" + _text(r[4]),
        "posted_at": datetime.fromtimestamp(r[12][0], timezone.utc) if r[12] else None,
        "locations": [loc[0] for loc in locs],
        "countries": list(dict.fromkeys(loc[5] for loc in locs if len(loc) > 5 and loc[5])),
    }


def list_jobs(c):
    jobs, page, total = [], 1, 1
    while (page - 1) * 20 < total:
        m = DATA.search(request("GET", URL, params={"page": page, "sort_by": "date"}).text)
        if not m:
            raise RuntimeError("Google results page format changed")
        d = json.loads(m.group(1))
        if not d[0]:
            break
        total = d[2]
        jobs += [_job(r) for r in d[0]]
        page += 1
        time.sleep(0.3)  # be polite: ~180 pages
    return jobs
