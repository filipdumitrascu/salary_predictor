"""Ashby public job board API: every job with its description in one request. Config: board."""

from ..fetch import get_json
from ..geo import countries_in

MODE = {"OnSite": "onsite", "Hybrid": "hybrid", "Remote": "remote"}
TYPE = {"FullTime": "full-time", "PartTime": "part-time", "Contract": "contract", "Temporary": "contract"}  # Intern is a level


def _place(location, address):
    a = (address or {}).get("postalAddress") or {}
    return ", ".join(filter(None, [a.get("addressLocality"), a.get("addressCountry")])) or location


def _compensation(j):
    comp = j.get("compensation") or {}
    summary = comp.get("scrapeableCompensationSalarySummary") or comp.get("compensationTierSummary")
    return f"<p>Compensation: salary range {summary}</p>" if summary else ""


def list_jobs(c):
    # includeCompensation: Ashby then also returns the pay range as a separate field ("$310K - $385K"),
    # which many companies (OpenAI) do not repeat in the description. It is appended to the description
    # so the same salary rules read it.
    d = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{c['board']}", params={"includeCompensation": "true"})
    jobs = []
    for j in d["jobs"]:
        if not j.get("isListed", True):
            continue
        locs = [_place(j.get("location"), j.get("address"))]
        locs += [_place(s.get("location"), s.get("address")) for s in j.get("secondaryLocations") or []]
        locs = [loc for loc in locs if loc]
        jobs.append({
            "source_id": j["id"],
            "title": j["title"],
            "url": j["jobUrl"],
            "description": (j.get("descriptionHtml") or "") + _compensation(j),
            "posted_at": j.get("publishedAt"),
            "locations": locs,
            "countries": list(dict.fromkeys(cc for loc in locs for cc in countries_in(loc))),
            "work_mode": MODE.get(j.get("workplaceType")),
            "employment_type": TYPE.get(j.get("employmentType")),
            "seniority": "intern" if j.get("employmentType") == "Intern" else None,
        })
    return jobs
