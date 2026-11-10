"""Tests of the extraction rules, on short examples with a known answer.

Run from the repository root:  python -m extraction.tests.test_extract   (or: pytest)
"""

import json
import tomllib
from pathlib import Path

from extraction import readers
from extraction.extract import _date, row
from extraction.geo import city_of, countries_in, place, us_state
from extraction.normalize import html_to_text, normalize, years_required
from extraction.readers import greenhouse
from extraction.readers.workday import _split
from extraction.salary import salary


def n(title, description="", **kw):
    return normalize({"title": title, "description": description, **kw})


def pay(text, country=None):
    """The salary as (min, max, currency, period), to compare briefly."""
    s = salary(text, country)
    return (s["min"], s["max"], s["currency"], s["period"]) if s else None


def test_seniority():
    assert n("Software Engineering Intern 2027")["seniority"] == "intern"
    assert n("Sr. Software Engineer")["seniority"] == "senior"
    assert n("Software Engineer III")["seniority"] == "senior"
    assert n("Software Engineer II")["seniority"] == "mid"
    assert n("Software Engineer I")["seniority"] == "entry"
    assert n("Staff Engineer, Infra")["seniority"] == "staff"
    assert n("Engineering Manager, Payments")["seniority"] == "lead"
    assert n("Senior Product Manager")["seniority"] == "senior"  # product manager is a role, not a level
    assert n("Product Manager")["seniority"] is None
    assert n("Working Student Embedded")["seniority"] == "intern"
    assert n("Account Executive, International")["seniority"] != "intern"  # "International" is not "intern"
    assert n("Backend Developer")["seniority"] is None  # unknown beats a wrong guess


def test_seniority_source():
    assert n("Sr. Software Engineer")["seniority_source"] == "title"
    j = n("Backend Developer", "3+ years of experience with Go")
    assert (j["seniority"], j["years_min"]) == (None, 3)  # the level is not estimated from the years
    assert n("Engineer", seniority="intern")["seniority_source"] == "platform"
    assert n("Backend Developer")["seniority_source"] is None


def test_role_family():
    assert n("Embedded Software Engineer")["role_family"] == "hardware"
    assert n("Security Software Engineer")["role_family"] == "security"
    assert n("Data Engineer")["role_family"] == "data"
    assert n("Software Engineer in Test")["role_family"] == "qa"
    assert n("Full Stack Developer")["role_family"] == "software"
    assert n("Account Executive")["role_family"] == "sales"
    assert n("Pharmacist")["role_family"] == "other"


def test_text_fields():
    d = "<p>We work in a hybrid model, 3 days per week in the office.</p><ul><li>Bachelor's or Master's degree</li>" \
        "<li>5+ years of experience in C++</li><li>2 years of experience with Linux</li></ul>"
    j = n("C++ Developer", d)
    assert (j["work_mode"], j["office_days"], j["degree"]) == ("hybrid", 3, "bachelor")
    assert (j["years_min"], j["years_max"]) == (2, 5)  # both ends are kept
    assert "<" not in html_to_text(d) and "• 5+ years" in html_to_text(d)
    assert n("Cloud Engineer", "Experience with hybrid cloud and MS Office")["work_mode"] is None
    assert n("Cloud Engineer", "Experience with hybrid cloud and MS Office")["degree"] is None
    assert n("Engineer", work_mode="onsite", office_days=2)["work_mode"] == "hybrid"  # days beat labels
    assert n("Engineer", office_days=0)["work_mode"] == "remote"
    assert n("Fulfillment Intern", "Must be at least 18 years of age. Work experience a plus.")["years_min"] is None
    assert n("Account Executive", locations=["Poland - Remote"])["work_mode"] == "remote"
    assert n("Analyst", years_min=3)["years_min"] == 3  # stated by the platform


def test_skills():
    assert n("Backend Developer", "Python, Go and C++ on AWS; let's go home, no rust here")["skills"] == ["Python", "C++", "Go", "AWS"]
    assert n("Dev", "Java/Kotlin, Node.js, ASP.NET, machine learning; excellent communication")["skills"] == \
        ["Java", "Kotlin", "Node.js", ".NET", "Machine Learning"]
    assert n("Embedded Software Engineer")["skills"] == ["Embedded"]  # the title counts too


def test_salary():
    assert pay("US: $307000 - $427000 (USD) + 30% bonus") == (307000, 427000, "USD", "year")
    assert pay("The U.S. pay range for this position is $148,100 - $282,100 annually.") == (148100, 282100, "USD", "year")
    assert pay("base pay ranges from $104,000/year in our lowest geographic market up to $185,000/year") == (104000, 185000, "USD", "year")
    assert pay("Expected annual base salary for this role is $65,500-71,500 plus bonus") == (65500, 71500, "USD", "year")
    assert pay("The US base salary range for this full-time position is $141,000-$202,000 + bonus + equity") == (141000, 202000, "USD", "year")
    assert pay("base salary range is $24.00 - $35.00/hr with overtime") == (24, 35, "USD", "hour")
    assert pay("The minimum salary is EUR 2.800,- gross/month") == (2800, None, "EUR", "month")
    assert pay("annual base salary range is $120,000 to $155,000 CAD.") == (120000, 155000, "CAD", "year")
    assert pay("Salariu: 8000 - 12000 RON brut lunar") == (8000, 12000, "RON", "month")
    assert pay("Salário: R$ 13.900 por mês") == (13900, None, "BRL", "month")
    assert pay("base salary $90,000 - $110,000", "CA") == (90000, 110000, "CAD", "year")  # "$" in Canada
    assert pay("The expected salary range for this position is: Annual Salary: $340,000—$425,000 USD") == (340000, 425000, "USD", "year")
    assert pay("Compensation: salary range $310K – $385K • Offers Equity") == (310000, 385000, "USD", "year")  # Ashby
    assert pay("Annual Salary:\n$320,000—$405,000 USD") == (320000, 405000, "USD", "year")  # Greenhouse (Anthropic)
    for not_pay in ["Amazon will invest $2.5 billion dollars", "an accident resulting in more than $5,000 in damages",
                    "a $100B market opportunity", "Pay: $10,000 sign-on bonus available",
                    "Salary range includes a sign-on bonus of $4,500 for this role",
                    "This role is eligible for a sign-on bonus, paid in two parts: $8,625 at hire"]:
        assert salary(not_pay) is None, not_pay


def test_salary_period():
    s = salary("The pay range is $120,000 - $150,000")  # no period written: 120,000 can only be yearly
    assert (s["period"], s["period_source"]) == ("year", "inferred")
    assert salary("The pay range is $120,000 - $150,000 per year")["period_source"] == "stated"
    assert salary("Base salary: £580 depending on experience") is None  # 580 what? not guessed
    assert salary("Salary: 8,625 USD") is None  # monthly? a bonus? not guessed
    assert pay("Salary: $8,625 per month") == (8625, None, "USD", "month")  # stated: fine


def test_salary_text():
    s = salary("Great team. The U.S. pay range for this position is $148,100 - $282,100 annually. Benefits...")
    assert "$148,100 - $282,100" in s["text"]


def test_salary_romanian():
    assert pay("Salariul de incadrare este in intervalul de 7000 lei brut si 13000 lei brut", "RO") == (7000, 13000, "RON", "month")
    assert pay("Salariul brut: 15000 lei", "RO") == (15000, None, "RON", "month")


def test_countries_and_cities():
    assert countries_in("Bucharest, Romania") == ["RO"]
    assert countries_in("Dublin, IE; London, UK") == ["IE", "GB"]
    assert countries_in("Los Gatos, California, United States of America") == ["US"]
    assert countries_in("Remote") == []
    assert city_of("USA - Sunnyvale, CA") == "Sunnyvale"
    assert city_of("United Kingdom, Edinburgh, SC, Freer Building") == "Edinburgh"
    assert city_of("US, Oregon, Hillsboro") == "Hillsboro"
    assert city_of("New York, NY, USA") == "New York"  # a city with a state's name still works when first
    assert city_of("Iași, IS, Romania") == "Iasi"
    assert city_of("Remote") is None and city_of("N/A") is None and city_of("RO") is None


def test_us_state():
    assert us_state("Seattle, WA, USA") == "WA"
    assert us_state("Austin, TX") == "TX"  # no country written
    assert us_state("US, California, Santa Clara") == "CA"
    assert us_state("Virginia - Mclean") == "VA"
    assert us_state("Los Gatos, California, United States of America") == "CA"
    assert us_state("New York, NY, USA") == "NY"
    assert us_state("Washington, DC") == "DC"
    assert us_state("Seattle, Washington, United States") == "WA"
    assert us_state("MD, US") == "MD"
    assert us_state("MA - Lawrence", ["US"]) == "MA"
    assert us_state("Austin, United States") == "TX"  # from the list of large cities
    assert us_state("Arlington, United States") is None  # Virginia or Texas: not guessed
    assert us_state("San Jose", ["US"]) == "CA"
    assert us_state("Hyderabad, TS, IN", ["IN"]) is None  # IN is India here, not Indiana
    assert us_state("Toronto, ON, CA", ["CA"]) is None  # CA is Canada here, not California
    assert us_state("Ottawa, ON, CA", ["CA"]) is None
    assert us_state("Bucharest, Romania") is None


def test_place():
    assert place("Austin, TX", []) == {"country": "US", "state": "TX", "city": "Austin"}
    assert place("Hyderabad, TS, IN", ["IN"]) == {"country": "IN", "state": None, "city": "Hyderabad"}
    assert place("Washington, DC", ["US"]) == {"country": "US", "state": "DC", "city": "Washington"}
    assert place("Remote", ["US"]) == {"country": "US", "state": None, "city": None}


def test_row():
    job = {"company": "x", "source_id": "1", "title": "Senior Data Engineer", "url": "u", "posted_at": "2026-10-01T10:00:00Z",
           "collected_at": "2026-11-05T08:00:00+00:00", "locations": ["Austin, TX", "Seattle, WA, USA"], "countries": [],
           "description": "<p>Python, SQL. The base pay range is $150,000 - $190,000 per year.</p>"}
    r = row(job, {"name": "X", "industry": "software_internet"})
    assert r["countries"] == "US" and r["states"] == "TX | WA" and r["cities"] == "Austin, TX | Seattle, WA"
    assert (r["salary_min"], r["salary_max"], r["salary_currency"]) == (150000, 190000, "USD")
    assert (r["posted_date"], r["n_locations"], r["skills"], r["seniority"]) == ("2026-10-01", 2, "Python | SQL", "senior")


def test_date():
    assert _date("2026-10-01T10:00:00Z") == "2026-10-01"
    assert _date("October 1, 2026") == "2026-10-01"
    assert _date(1790000000) is not None and _date(1790000000000) == _date(1790000000)
    assert _date("2999-01-01") is None and _date("soon") is None and _date(None) is None


def test_workday_split():
    f = [{"facetParameter": "timeType", "values": [{"id": "a", "count": 2725}, {"id": "b", "count": 4}]},
         {"facetParameter": "jobFamilyGroup", "values": [{"id": "x", "count": 1732}, {"id": "y", "count": 997}]},
         {"facetParameter": "workerSubType", "values": [{"id": "z", "count": 900}]}]
    assert _split(f) == ("jobFamilyGroup", ["x", "y"])
    assert _split(f[:1]) is None


def test_companies_config():
    path = Path(__file__).resolve().parent.parent / "companies.toml"
    companies = tomllib.loads(path.read_text(encoding="utf-8"))["company"]
    slugs = [c["slug"] for c in companies]
    assert len(slugs) == len(set(slugs)), "duplicate slug"
    for c in companies:
        assert c["platform"] in readers.ALL, c["slug"]
        assert c.get("industry"), c["slug"]


def test_fixes_found_on_live_data():
    assert salary("Local Pay Range $95,000—$95,000 USD")["max"] == 95000
    assert years_required("3-5 years of experience") == (3, 5)
    assert years_required("Over 100 years of industry leadership") == (None, None)
    assert us_state("Chennai, TN, IN", ["IN"]) is None
    assert us_state("Ottawa, ON, CA", ["US", "CA"]) is None
    assert us_state("Seattle, WA, US") == "WA"
    r = row({"company": "x", "source_id": "1", "title": "E", "locations": ["Toronto, Canada", "Austin, TX"],
             "description": "Salary range $150,000 - $200,000"}, {})
    assert r["salary_currency"] == "USD"  # a US job: "$" is not read as Canadian


def test_greenhouse_locations():
    job = {"location": {"name": "San Francisco, CA | New York City, NY; Remote"}, "offices": []}
    assert greenhouse._places(job) == ["San Francisco, CA", "New York City, NY", "Remote"]
    cloudflare = {"location": {"name": "Hybrid"}, "offices": [{"name": "Austin, TX"}, {"name": "Lisbon, Portugal"}]}
    assert greenhouse._places(cloudflare) == ["Austin, TX", "Lisbon, Portugal"]
    assert greenhouse._work_mode(cloudflare) == "hybrid"
    assert greenhouse._work_mode({"location": {"name": "Hybrid; In-Office"}}) is None


def test_apple_page():
    from extraction.readers.apple import page_text
    data = {"translations": {"common": {"noJavascript": "Please enable Javascript in your browser for best experience."}},
            "jobDetails": {"positionId": "200", "description": "You will plan content for AI search and work with teams.",
            "minimumQualifications": "5+ years of experience in content strategy and SEO.",
            "payAndBenefits": {"content": "At Apple, base pay is one part of our total compensation package and is determined "
                               "within a range. Your base pay will be between $171,600 and $280,000, and your base pay "
                               "will depend on your skills."}}}
    literal = json.dumps(json.dumps(data))  # how the page carries it: a JS string holding JSON
    page = f"<html><script>window.__staticRouterHydrationData = JSON.parse({literal});</script></html>"
    text = page_text(page)
    assert "5+ years" in text and "Javascript" not in text
    j = n("AI Optimization Content Strategist", text)
    assert (j["salary_min"], j["salary_max"], j["salary_period"], j["years_min"]) == (171600, 280000, "year", 5)


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("test_")]
    for name, fn in tests:
        fn()
    print(f"ok: {len(tests)} tests passed")
