"""Accenture careers API. Config: country_sites (e.g. ["us-en"]): the API answers one country per site."""

from ..fetch import request
from ..geo import countries_in

PAGE = 100


def list_jobs(c):
    return [job for site in c["country_sites"] for job in _site(site)]


def _site(site):
    jobs, start, total = [], 0, 1
    while start < total:
        form = {"startIndex": start, "maxResultSize": PAGE, "jobKeyword": "", "jobCountry": "", "jobLanguage": "en",
                "countrySite": site, "sortBy": "0"}
        d = request("POST", "https://www.accenture.com/api/accenture/elastic/findjobs", files={k: (None, str(v)) for k, v in form.items()}).json()
        total, page = d["totalHits"]["total"], d["data"]
        if not page:
            break
        for j in page:
            locs = [f"{city}, {j['country']}" for city in j.get("location") or []] or [j["country"]]
            years = (j.get("yearsOfExperience") or "").split("-")[0]
            jobs.append({
                "source_id": j["requisitionId"],
                "title": j["title"],
                "url": j["jobDetailUrl"].replace("{0}", site),
                "description": (j.get("jobDescription") or "") + (j.get("qualification") or ""),
                "posted_at": j.get("updateDate"),
                "locations": locs,
                "countries": countries_in(j.get("country") or ""),
                "years_min": int(years) if years.isdigit() else None,
                "work_mode": "hybrid" if "hybrid" in (j.get("remoteType") or "").lower() else None,
            })
        start += len(page)
    return jobs
