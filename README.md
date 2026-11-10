# Salary prediction from US job ads

Predicting the **yearly salary (USD)** offered in a US job ad from the ad itself: title, seniority,
role, location, work mode, years of experience and degree asked, skills, company and its industry.

The dataset is built from scratch: job ads are collected directly from the official careers sites
of 45 companies. Many US states require job ads to state a pay range (California, Washington,
New York, Colorado and others), so US ads give both the features and the target.

> Status: collection and field extraction are in this repository. Preprocessing, exploratory analysis
> and the models come next.

## Pipeline

```
companies.toml ──crawl.py──▶ data/raw/<company>.jsonl.gz ──extract.py──▶ data/intermediate/jobs.csv ──▶ preprocessing
   (sources)        (1) collect                               (2) fields from text, US only        (next)
```

Each step reads the previous step's files and writes new ones; collected data is never edited.
If an extraction rule turns out to be wrong, it is fixed in the rules and `extract.py` is run again
in seconds, without collecting again. A change in a reader (a field it did not save) needs collecting again.

| Step | Script | Does | Does not |
|---|---|---|---|
| 1 | `extraction/crawl.py` | reads every company's job list and job pages, saves the fields each reader keeps (title, full description, locations, url, date...) | extract or change the text |
| 2 | `extraction/extract.py` | keeps the US ads and turns each one into a row: seniority, role, years, degree, skills, work mode, city, US state, salary as stated | remove duplicates, convert salaries, fill missing values or remove wrong values |

## Data sources

Ads are read from the companies' own careers sites, through the public APIs of the hiring
platforms the companies use (one reader per platform in `extraction/readers/`):

| Platform | Companies |
|---|---|
| Workday | Salesforce, CrowdStrike, Adobe, NVIDIA, Intel, Analog Devices, Microchip, NXP, Cisco, HP, Deutsche Bank, LSEG, BorgWarner |
| Greenhouse | Anthropic, Databricks, Datadog, Airbnb, Cloudflare, DRW, Hudson River Trading, IMC, Optiver, Jump Trading, Stripe, Adyen |
| Eightfold | Microsoft, Infineon, Ericsson, Netflix |
| SmartRecruiters | Nagarro, Bosch, Continental |
| iCIMS Jibe | Keysight, Susquehanna (SIG) |
| Ashby, Lever, Oracle Cloud, Phenom, Avature, Radancy | OpenAI, Spotify, Oracle, Thales, Lenovo, ING |
| Company's own site | Amazon, Apple, Google, Atlassian, Accenture |

**How the companies were chosen.** 41 companies with at least 10 such ads are kept, plus Cloudflare,
OpenAI and Apple, whose salaries are recovered by reader fixes, and Anthropic, added by hand (see `companies.toml`). Each company's
**industry** is set by hand in `companies.toml` (10 groups, e.g. `software_internet`,
`semiconductors`, `trading`, `banking_finance`, `automotive_industrial`). In total there are 45.

**Polite collection.** Only public job listings are read (the same data any visitor sees), at most
about 4 requests per second, with a User-Agent that says what the program is, and retrying with
growing pauses when a site answers "too many requests".

## How to run

Python 3.11 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m extraction.tests.test_extract      # the extraction rules' tests
python -m extraction.crawl                   # step 1: all companies (takes a few hours)
python -m extraction.crawl google stripe     #   or only some; saved companies are skipped, --force reads again
python -m extraction.extract                 # step 2: data/raw -> data/intermediate/jobs.csv
```

`data/raw/manifest.json` records, for each company, how many ads were read and when.

## The extracted dataset: `data/intermediate/jobs.csv`

One row per US job ad, with or without a salary. Unknown values are left empty (an empty `seniority`
means neither the platform nor the title states it). The file is not preprocessed: it still has
duplicates, missing values, salaries in different periods and wrong values. List columns separate
their values with ` | `.

| Column | Meaning | How it is obtained |
|---|---|---|
| `job_id` | `company:id on the platform` | platform |
| `company`, `company_name`, `industry` | the employer and its industry | `companies.toml` |
| `url` | the official job page | platform |
| `posted_date`, `collected_date` | when the ad was posted / read | platform / crawler |
| `title` | job title | platform |
| `seniority` | intern, entry, mid, senior, staff, lead, director | rules on the title (or stated by the platform) |
| `seniority_source` | where `seniority` came from: `platform` or `title` | |
| `role_family` | software, data, hardware, devops, security, qa, product, sales, ... or `other` | rules on the title |
| `years_min`, `years_max` | smallest and largest years of experience the ad mentions | rules on the description |
| `degree` | lowest degree asked: bachelor < master < phd | rules on the description |
| `skills` | technologies named in the ad (Python, AWS, SQL, ...; 43 tracked) | word list on title + description |
| `work_mode` | onsite, hybrid, remote | platform, else rules |
| `office_days` | office days per week, when stated | rules on the description |
| `employment_type` | full-time, part-time, contract | platform, else rules |
| `locations` | locations as written by the company | platform |
| `countries` | ISO codes of the job's countries | platform + rules (`geo.py`) |
| `states` | US state codes (CA, WA, ...) | rules (`geo.py`) |
| `cities` | cities, with the state for US ones ("Austin, TX") | rules (`geo.py`) |
| `n_locations` | number of distinct locations in the ad | count |
| `salary_min`, `salary_max` | the pay range as stated (`max` empty for "from X") | rules on the description (`salary.py`) |
| `salary_currency`, `salary_period` | USD, EUR, ... / year, month, hour | rules |
| `salary_period_source` | `stated` in the ad, or `inferred` from the amount (≥ 25,000 → yearly, < 200 → hourly) | |
| `salary_text` | the sentence the salary was read from, to check the rules by hand | |
| `description_chars` | length of the description read (0 = the site gave none) | |
| `detail_error` | set when a job's page could not be read | crawler |

The target for the model (yearly USD salary, the middle of the range) is built during preprocessing.

## Known limitations

- **Selection bias.** Only ads that state a salary can be used, and those come mostly from US
  states with pay-transparency laws and from large tech companies. The model describes these
  companies, not the whole US job market.
- **One company dominates.** Amazon has far more ads than any other company; this is not handled when
  collecting.
- **Some salaries are wrong.** The rules take the first amount with a pay word nearby, so another amount
  (a budget, a benefit) can be read as the salary. When an ad lists several ranges by zone or city,
  only the first is kept, even if it is not the zone of the job.
- **Ranges can cover all US locations.** Some companies (Amazon) state one range for every US market
  ("from $X in our lowest geographic market up to $Y"), so for them the salary does not depend on the city.
- **Rule-based extraction.** Fields are read with regular expressions, tested in
  `extraction/tests/`. Their accuracy is checked by hand on a random sample of ads (`salary_text`, `url`).
- **States.** Locations without a state (e.g. "Austin, United States") get one only for large
  cities with a single well-known state; others stay empty. "United States" / "Remote" ads have none,
  and neither do Apple's ads, whose list gives only the country.

## Repository

```
extraction/
  companies.toml      sources: companies, their platform settings, their industry
  readers/            one file per hiring platform (or company site)
  fetch.py            HTTP with a pause between requests and retries
  crawl.py            step 1
  normalize.py        rules: seniority, role, years, degree, skills, work mode, contract
  salary.py           rules: salary
  geo.py              rules: country, city, US state
  extract.py          step 2
  tests/              tests of the rules
data/
  raw/                step 1 output (one .jsonl.gz per company)
  intermediate/       step 2 output
docs/                 presentations and report
```
