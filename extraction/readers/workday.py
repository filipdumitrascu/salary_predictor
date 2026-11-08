"""Workday: one reader for every company on *.myworkdayjobs.com. Config: host, tenant, site."""

from ..fetch import get_json, post_json

PAGE = 20  # Workday's maximum


def _base(c):
    return f"https://{c['host']}/wday/cxs/{c['tenant']}/{c['site']}"


CAP = 2000  # Workday never pages past 2000 results and reports total = 2000 above that


def _page_all(c, facets):
    jobs, offset, total = [], 0, None
    while total is None or offset < total:
        d = post_json(f"{_base(c)}/jobs", {"limit": PAGE, "offset": offset, "searchText": "", "appliedFacets": facets})
        total = total or d["total"]  # only the first page reports the total
        if not d["jobPostings"]:
            break
        # some entries come without a link or title (Intel, NXP): skip them
        jobs += [{"source_id": p["externalPath"], "title": p["title"]} for p in d["jobPostings"] if p.get("externalPath") and p.get("title")]
        offset += PAGE
    return jobs


def _split(facets):
    """The filter that splits the jobs into groups Workday can page fully (each under the cap),
    covering the most jobs (e.g. NVIDIA: jobFamilyGroup). None if no filter does."""
    best = None
    for f in facets:
        values = [v for v in f.get("values", []) if "count" in v]
        if values and max(v["count"] for v in values) < CAP:
            covered = sum(v["count"] for v in values)
            if not best or covered > best[0]:
                best = (covered, f["facetParameter"], [v["id"] for v in values])
    return best and best[1:]


def list_jobs(c):
    first = post_json(f"{_base(c)}/jobs", {"limit": PAGE, "offset": 0, "searchText": "", "appliedFacets": {}})
    if first["total"] < CAP:
        return _page_all(c, {})
    split = _split(first.get("facets", []))
    if not split:
        raise RuntimeError(f"over {CAP} jobs and no filter splits them under {CAP}")
    param, ids = split
    jobs = {j["source_id"]: j for value in ids for j in _page_all(c, {param: [value]})}  # a job can be in two groups
    return list(jobs.values())


def detail(c, job):
    i = get_json(_base(c) + job["source_id"])["jobPostingInfo"]
    country = (i.get("jobRequisitionLocation") or {}).get("country") or {}
    time_type = (i.get("timeType") or "").lower()
    return {
        **job,
        "url": i["externalUrl"],
        "description": i.get("jobDescription"),
        "posted_at": i.get("startDate"),
        "locations": [i["location"], *i.get("additionalLocations", [])] if i.get("location") else [],
        # shortcut: Workday only gives the country of the main location, not of additionalLocations.
        "countries": [country["alpha2Code"]] if country.get("alpha2Code") else [],
        "employment_type": "part-time" if "part" in time_type else "full-time" if "full" in time_type else None,
    }
