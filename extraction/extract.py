"""Step 2: read the raw jobs saved by crawl.py and extract one row of fields per job.

Usage (from the repository root):
    python -m extraction.extract

Input:  data/raw/*.jsonl.gz      (written by crawl.py)
Output: data/intermediate/jobs.csv    every US job, with or without a salary

Only the US jobs are kept, because the project is about them. Nothing else is removed or converted
(no salary conversion, no duplicate removal, no missing values filled): that is preprocessing, done
after this step. This step only turns text into fields.
List columns (locations, countries, cities, states, skills) separate their values with " | ".
"""

import csv
import gzip
import json
import re
import sys
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .geo import place
from .normalize import normalize

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "intermediate" / "jobs.csv"
COMPANIES = Path(__file__).resolve().parent / "companies.toml"

COLUMNS = [
    # identity and source
    "job_id", "company", "company_name", "industry", "url", "posted_date", "collected_date",
    # the ad
    "title", "seniority", "seniority_source", "role_family", "years_min", "years_max", "degree", "skills",
    "work_mode", "office_days", "employment_type",
    # where
    "locations", "countries", "states", "cities", "n_locations",
    # the target (salary as stated in the ad, not converted yet)
    "salary_min", "salary_max", "salary_currency", "salary_period", "salary_period_source", "salary_text",
    # checks
    "description_chars", "detail_error",
]
SEP = " | "


def _date(value) -> str | None:
    """YYYY-MM-DD from the many date forms platforms use; None if it cannot be read or is in the future."""
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        seconds = float(value) / (1000 if float(value) > 1e11 else 1)  # milliseconds or seconds since 1970
        day = datetime.fromtimestamp(seconds, timezone.utc).date()
    else:
        s = str(value).strip()
        day = None
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            day = datetime.strptime(s[:10], "%Y-%m-%d").date()
        else:
            for fmt in ("%B %d, %Y", "%b %d, %Y", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    day = datetime.strptime(s, fmt).date()
                    break
                except ValueError:
                    pass
        if day is None:
            return None
    return day.isoformat() if day <= datetime.now(timezone.utc).date() else None


def _join(values) -> str:
    return SEP.join(str(v) for v in dict.fromkeys(v for v in values if v))


def row(job: dict, company: dict) -> dict:
    # "Bucharest, Bucharest, Romania" -> "Bucharest, Romania"
    locations = [", ".join(dict.fromkeys(p.strip() for p in str(loc).split(","))) for loc in job.get("locations") or [] if loc]
    job_countries = [c.upper() for c in job.get("countries") or [] if c]
    places = [place(loc, job_countries) for loc in locations]
    # a location that names a US state is in the US even if the platform gave no country ("Austin, TX")
    countries = list(dict.fromkeys(job_countries + [p["country"] for p in places if p["country"]]))
    cities = [f"{p['city']}, {p['state']}" if p["state"] and p["city"] else p["city"] for p in places]

    f = normalize(job, "US" if "US" in countries else countries[0] if countries else None)
    return {
        "job_id": f"{job['company']}:{job['source_id']}",
        "company": job["company"],
        "company_name": company.get("name"),
        "industry": company.get("industry"),
        "url": job.get("url"),
        "posted_date": _date(job.get("posted_at")),
        "collected_date": _date(job.get("collected_at")),
        **{k: f[k] for k in ("title", "seniority", "seniority_source", "role_family", "years_min", "years_max",
                              "degree", "work_mode", "office_days", "employment_type")},
        "skills": _join(f["skills"]),
        "locations": _join(locations),
        "countries": _join(countries),
        "states": _join(p["state"] for p in places),
        "cities": _join(cities),
        "n_locations": len(set(locations)),
        **{k: f[k] for k in ("salary_min", "salary_max", "salary_currency", "salary_period",
                              "salary_period_source", "salary_text", "description_chars")},
        "detail_error": job.get("detail_error"),
    }


def read_raw(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main() -> int:
    companies = {c["slug"]: c for c in tomllib.loads(COMPANIES.read_text(encoding="utf-8"))["company"]}
    files = sorted(RAW.glob("*.jsonl.gz"))
    if not files:
        print(f"no raw files in {RAW}: run `python -m extraction.crawl` first", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    collected, us_jobs, with_salary, by_company = 0, 0, 0, Counter()
    with open(OUT, "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, COLUMNS)
        writer.writeheader()
        for path in files:
            for job in read_raw(path):
                collected += 1
                r = row(job, companies.get(job["company"], {}))
                if "US" not in r["countries"].split(SEP):
                    continue
                writer.writerow(r)
                us_jobs += 1
                with_salary += r["salary_min"] is not None
                by_company[r["company"]] += 1

    print(f"collected: {collected} jobs from {len(files)} companies")
    print(f"US jobs: {us_jobs} -> {OUT.relative_to(ROOT)}")
    print(f"US jobs with a salary: {with_salary}")
    print("most US jobs:", ", ".join(f"{c} {n}" for c, n in by_company.most_common(8)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
