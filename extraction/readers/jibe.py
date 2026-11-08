"""iCIMS "Jibe" careers sites (Booking.com, SIG, Keysight): a JSON API with every job and its description.
Config: base (site root), job_path (where a job's page lives, e.g. "/booking/jobs" -> {base}/booking/jobs/{id})."""

from ..fetch import get_json

PAGE = 100


def list_jobs(c):
    jobs, page, total = [], 1, 1
    while len(jobs) < total:
        d = get_json(f"{c['base']}/api/jobs", params={"page": page, "limit": PAGE})
        total = d["totalCount"]
        if not d["jobs"]:
            break
        for j in (x["data"] for x in d["jobs"]):
            jobs.append({
                "source_id": j["req_id"],
                "title": j["title"],
                "url": f"{c['base']}{c['job_path']}/{j['slug']}",
                "description": " ".join(filter(None, [j.get("description"), j.get("responsibilities"), j.get("qualifications")])),
                "posted_at": j.get("posted_date"),
                "locations": [j["full_location"]] if j.get("full_location") else [],
                "countries": [j["country_code"]] if j.get("country_code") else [],
            })
        page += 1
    return jobs
