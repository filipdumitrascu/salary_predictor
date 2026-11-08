"""Oracle Cloud recruiting sites (Oracle, Nokia...). Config: host (the *.oraclecloud.com host), site (e.g. CX_1)."""

from ..fetch import get_json

PAGE = 200
MODE = {"hybrid": "hybrid", "on-site": "onsite", "onsite": "onsite", "remote": "remote"}


def _get(c, resource, finder, **extra):
    # finder is passed literally: Oracle rejects it when its ";" and "," are percent-encoded
    query = "&".join([f"{k}={v}" for k, v in {"onlyData": "true", **extra}.items()] + [f"finder={finder}"])
    return get_json(f"https://{c['host']}/hcmRestApi/resources/latest/{resource}?{query}")["items"]


def list_jobs(c):
    jobs, offset, total = [], 0, 1
    while offset < total:
        d = _get(c, "recruitingCEJobRequisitions", f"findReqs;siteNumber={c['site']},limit={PAGE},offset={offset},sortBy=POSTING_DATES_DESC",
                 expand="requisitionList.secondaryLocations")[0]
        total, page = d["TotalJobsCount"], d["requisitionList"]
        if not page:
            break
        for r in page:
            secondary = r.get("secondaryLocations") or []
            jobs.append({
                "source_id": r["Id"],
                "title": r["Title"],
                "url": f"https://{c['host']}/hcmUI/CandidateExperience/en/sites/{c['site']}/job/{r['Id']}",
                "posted_at": r.get("PostedDate"),
                "locations": list(dict.fromkeys(filter(None, [r.get("PrimaryLocation"), *(s.get("Name") for s in secondary)]))),
                "countries": list(dict.fromkeys(filter(None, [r.get("PrimaryLocationCountry"), *(s.get("CountryCode") for s in secondary)]))),
                "work_mode": MODE.get((r.get("WorkplaceType") or "").lower()),
            })
        offset += len(page)
    return jobs


def detail(c, job):
    d = _get(c, "recruitingCEJobRequisitionDetails", f'ById;Id="{job["source_id"]}",siteNumber={c["site"]}', expand="all")[0]
    parts = ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")
    return {**job, "description": "".join(d.get(k) or "" for k in parts)}
