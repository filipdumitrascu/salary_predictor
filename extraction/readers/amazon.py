"""amazon.jobs search JSON. Results stop at 10,000 per query, so we query per country,
and split big countries (the US) by business category.
Config: countries (optional list of the site's three-letter codes, e.g. ["USA"]); without it every country is read."""

import json
from datetime import datetime

from ..fetch import get_json

BASE = "https://www.amazon.jobs/en/search.json"
PAGE = 100
QUERY_CAP = 9000  # stay safely under the 10,000 result limit


def _facet(params, name):
    d = get_json(BASE, params={**params, "result_limit": 1, "facets[]": name})
    return [(k, v) for item in d["facets"][f"{name}_facet"] for k, v in item.items()]


def _first(d, *keys):
    return next((d[k] for k in keys if d.get(k)), None)


def _job(j):
    locs = [json.loads(s) for s in j.get("locations") or []]
    mode = {(loc.get("type") or "").lower() for loc in locs} & {"onsite", "remote", "hybrid"}
    return {
        "source_id": j["id_icims"],
        "title": j["title"],
        "url": "https://www.amazon.jobs" + j["job_path"],
        "description": "<br/><br/>".join(filter(None, [
            j.get("description"),
            j.get("basic_qualifications") and "<h3>Basic qualifications</h3>" + j["basic_qualifications"],
            j.get("preferred_qualifications") and "<h3>Preferred qualifications</h3>" + j["preferred_qualifications"],
        ])),
        "posted_at": datetime.strptime(j["posted_date"], "%B %d, %Y").date().isoformat() if j.get("posted_date") else None,
        # City, state, country. The state is needed for US jobs ("Arlington" is in Virginia and in Texas).
        "locations": [", ".join(filter(None, [
            loc.get("normalizedCityName"),
            _first(loc, "normalizedStateName", "normalizedState", "state", "region"),
            loc.get("normalizedCountryName"),
        ])) for loc in locs] or [j.get("normalized_location") or j.get("location")],
        "countries": list(dict.fromkeys(loc["countryIso2a"] for loc in locs if loc.get("countryIso2a")))
                     or ([j["country_code"]] if len(j.get("country_code") or "") == 2 else []),
        "work_mode": mode.pop() if len(mode) == 1 else None,
        "employment_type": j.get("job_schedule_type") if j.get("job_schedule_type") in ("full-time", "part-time") else None,
        "seniority": "intern" if j.get("is_intern") else None,
    }


def list_jobs(c):
    wanted = set(c.get("countries") or [])
    queries = []
    for country, count in _facet({}, "normalized_country_code"):
        if wanted and country not in wanted:
            continue
        if count < QUERY_CAP:
            queries.append({"country": country})
        else:
            # A job with no business category in a >9000-job country is missed (rare).
            queries += [{"country": country, "business_category[]": cat} for cat, _ in _facet({"country": country}, "business_category")]

    jobs = {}
    for q in queries:
        for offset in range(0, QUERY_CAP + PAGE, PAGE):
            page = get_json(BASE, params={**q, "result_limit": PAGE, "offset": offset, "sort": "recent"})["jobs"] or []
            jobs.update((j["id_icims"], _job(j)) for j in page)
            if len(page) < PAGE:
                break
    return list(jobs.values())
