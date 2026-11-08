"""SmartRecruiters public postings API. Config: board (the company identifier in the URL)."""

from ..fetch import get_json

PAGE = 100
SENIORITY = {"internship": "intern", "entry_level": "entry", "director": "director", "executive": "director"}


def _employment(label: str) -> str | None:
    label = label.lower()
    for key, value in [("part", "part-time"), ("contract", "contract"),  # internship is a level, not a type
                       ("temporary", "contract"), ("full", "full-time"), ("permanent", "full-time")]:
        if key in label:
            return value
    return None


def list_jobs(c):
    base = f"https://api.smartrecruiters.com/v1/companies/{c['board']}/postings"
    jobs, offset, total = [], 0, 1
    while offset < total:
        d = get_json(base, params={"limit": PAGE, "offset": offset})
        total = d["totalFound"]
        if not d["content"]:
            break
        for p in d["content"]:
            loc = p.get("location") or {}
            jobs.append({
                "source_id": p["id"],
                "title": p["name"],
                "url": f"https://jobs.smartrecruiters.com/{c['board']}/{p['id']}",
                "posted_at": p.get("releasedDate"),
                "locations": [loc["fullLocation"]] if loc.get("fullLocation") else [],
                "countries": [loc["country"].upper()] if loc.get("country") else [],
                "work_mode": "remote" if loc.get("remote") else "hybrid" if loc.get("hybrid") else None,
                "employment_type": _employment((p.get("typeOfEmployment") or {}).get("label", "")),
                "seniority": SENIORITY.get((p.get("experienceLevel") or {}).get("id")),
            })
        offset += PAGE
    return jobs


def detail(c, job):
    d = get_json(f"https://api.smartrecruiters.com/v1/companies/{c['board']}/postings/{job['source_id']}")
    sections = d.get("jobAd", {}).get("sections", {})
    parts = [sections.get(k) or {} for k in ("jobDescription", "qualifications", "additionalInformation")]
    return {
        **job,
        "url": d.get("postingUrl") or job["url"],
        "description": "".join(f"<h3>{s.get('title', '')}</h3>{s.get('text', '')}" for s in parts if s.get("text")),
    }
