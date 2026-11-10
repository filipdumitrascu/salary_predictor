# Salary prediction from US job ads

Predicting the **yearly salary (USD)** offered in a US job ad from the ad itself: title, seniority,
role, location, work mode, years of experience and degree asked, skills, company and its industry.

The dataset is built from scratch: job ads are collected directly from the official careers sites
of 45 companies. Many US states require job ads to state a pay range (California, Washington,
New York, Colorado and others), so US ads give both the features and the target.


## Pipeline

```
companies.toml ────crawl.py──▶ data/raw/<company>.jsonl.gz ──────extract.py─────▶ data/intermediate/jobs.csv
  (sources)       (1) collect                              (2) fields from text, US only
```

```
data/intermediate/jobs.csv ──measuring_data.ipynb──▶ tables + docs/figures/*.png      (3) measure, nothing is changed

data/intermediate/jobs.csv ──clean.py──▶ jobs_clean.csv ──integrate.py──▶ jobs_integrated.csv ──▶ transformation, reduction, discretization (next) ──▶ model
```

Each step reads the previous step's files and writes new ones; collected data is never edited.
If an extraction rule turns out to be wrong, it is fixed in the rules and `extract.py` is run again
in seconds, without collecting again. A change in a reader (a field it did not save) needs collecting again.

| Step | Script | Does | Does not |
|---|---|---|---|
| 1 | `extraction/crawl.py` | reads every company's job list and job pages, saves the fields each reader keeps (title, full description, locations, url, date...) | extract or change the text |
| 2 | `extraction/extract.py` | keeps the US ads and turns each one into a row: seniority, role, years, degree, skills, work mode, city, US state, salary as stated | remove duplicates, convert salaries, fill missing values or remove wrong values |
| 3 | `preprocessing/measuring_data.ipynb` | measures every column by its scale, draws the plots | change the data |
| 4 | `preprocessing/clean.py` | missing values, wrong salaries, noise in titles | remove duplicates, convert salaries |
| 5 | `preprocessing/integrate.py` | duplicates, salary units, redundant columns | build the target, encode, scale |

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


## Preprocessing
### 1. Data Types

#### Categorical
##### Nominal
- title (Senior Software Engineer)
- role_family (software, hardware, data)
- cities (Austin, TX) - several values per ad
- states (CA, WA) - several values per ad
- industry (semiconductors)
- company (Amazon)
- salary_currency (USD, EUR, CAD)
- salary_period (year, hour, month)

##### Binary
- skills (Python, AWS, ...) - 43 asymmetric binary attributes: only "the ad names it" matters
- seniority_source (platform / title) - symmetric
- salary_period_source (stated / inferred) - symmetric

##### Ordinal
- seniority (intern < entry < mid < senior < staff < lead < director)
- degree (bachelor < master < phd)
- work_mode (remote < hybrid < onsite) - ordered by days in the office
- employment_type (contract < part-time < full-time)

#### Numerical
##### Discrete
- years_min - ratio
- years_max - ratio
- office_days - ratio
- n_locations - ratio
- description_chars - ratio
- posted_date - interval (days; the zero is arbitrary, only differences make sense)

##### Continuous
- salary_min - ratio
- salary_max - ratio

#### Not measured
- job_id, url, company_name, locations, countries, salary_text, detail_error: identifiers, raw text and checks
- collected_date: one value for every row (the day of the crawl)

Which measures each scale allows:
| Scale | Measures |
|---|---|
| nominal, binary | frequency, mode |
| ordinal | + median, quartiles, min, max (positions in the order) |
| interval | + mean, range, IQR, std, skewness, kurtosis (on differences) |
| ratio | all of them; ratios ("twice as much") make sense |


### 2. Measuring Data

Notebook `preprocessing/measuring_data.ipynb`, on `data/intermediate/jobs.csv` (32,010 ads, 31 columns),
before any change. Each column gets the measures its scale allows (table above). Columns with several
values in a cell (`states`, `cities`, `skills`) are split first; their percentages are "% of ads", so they
add up to more than 100%. A mode is always shown with the share of missing values next to it.

#### Missing values

| Column | Missing | Column | Missing |
|---|---|---|---|
| office_days | 95.7% | skills | 31.7% |
| work_mode | 45.6% | years_min, years_max | 29.7% |
| seniority | 42.5% | salary_max | 17.5% |
| employment_type | 36.6% | states / cities | 16.2% / 15.9% |
| degree | 33.1% | salary_min, currency, period | 15.3% |
| posted_date | 1.4% | | |

![missing values](docs/figures/missing.png)

#### Nominal and binary: frequency, mode

| Column | Mode | Mode % | Distinct | Missing |
|---|---|---|---|---|
| company | amazon | 39.0% | 45 | 0% |
| industry | software_internet | 65.4% | 10 | 0% |
| role_family | other | 18.9% | 18 | 0% |
| states | CA | 29.0% | 51 | 16.2% |
| cities | Seattle, WA | 16.3% | 1,368 | 15.9% |
| title | Area Manager II | 0.7% | 23,379 | 0% |
| salary_currency | USD | 84.6% | 3 | 15.3% |
| salary_period | year | 80.9% | 3 | 15.3% |
| seniority_source | title | 57.0% | 2 | 42.5% |
| salary_period_source | stated | 55.7% | 2 | 15.3% |

`skills`: AWS is in 22.8% of the ads, Python 22.1%, Machine Learning 18.6%; 31.7% name none of the 43.

![ads per company](docs/figures/company.png)

#### Ordinal: frequency, mode, median, quartiles

The median and quartiles are positions in the order, so they are always a category; a mean is not allowed.

| Column | Min | Q1 | Median | Q3 | Max | Mode | Missing |
|---|---|---|---|---|---|---|---|
| seniority | intern | senior | staff | lead | director | senior | 42.5% |
| degree | bachelor | bachelor | bachelor | bachelor | phd | bachelor | 33.1% |
| work_mode | remote | hybrid | onsite | onsite | onsite | onsite | 45.6% |
| employment_type | contract | full-time | full-time | full-time | full-time | full-time | 36.6% |

![seniority](docs/figures/seniority.png)

#### Numeric: mean, median, mode, midrange, range, percentiles, IQR, five-number summary, std, variance, skewness, kurtosis

The full table is in the notebook; std and variance are the sample ones, kurtosis is the excess kurtosis
(0 for a normal distribution), outliers are values outside [Q1 - 1.5 IQR, Q3 + 1.5 IQR], counted only.

| Column | Mean | Median | Min | Q1 | Q3 | Max | Std | Skewness | Kurtosis | Outliers |
|---|---|---|---|---|---|---|---|---|---|---|
| years_min | 4.74 | 4 | 0 | 2 | 7 | 20 | 3.22 | 1.04 | 1.04 | 293 |
| years_max | 6.05 | 5 | 0 | 3 | 8 | 20 | 3.42 | 0.67 | 0.17 | 85 |
| office_days | 2.62 | 3 | 0 | 3 | 3 | 5 | 1.45 | -0.74 | -0.19 | 519 |
| n_locations | 2.49 | 1 | 0 | 1 | 2 | 121 | 5.84 | 6.44 | 44.98 | 3,522 |
| description_chars | 7,517 | 6,427 | 74 | 4,863 | 8,357 | 26,702 | 4,138 | 1.56 | 1.81 | 3,624 |

**Salary (the target).** Measured over all rows and per pay period (USD only):

| | Count | Mean | Median | Min | P5 | Q1 | Q3 | Max | Midrange | Std | Skewness | Kurtosis | Outliers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| salary_min, all rows | 27,118 | 142,392 | 142,300 | 5 | 51,400 | 102,300 | 174,000 | 890,000 | 445,003 | 66,870 | 1.2 | 5.4 | 895 |
| salary_min, year | 25,868 | 149,144 | 143,700 | 8,625 | 70,350 | 111,300 | 175,000 | 890,000 | 449,313 | 60,721 | 1.9 | 7.6 | 1,048 |
| salary_max, year | 25,349 | 230,508 | 215,300 | 49,920 | 117,100 | 182,700 | 270,200 | 1,690,000 | 869,960 | 87,715 | 2.4 | 15.1 | 917 |
| salary_min, hour | 1,178 | 31.6 | 28.0 | 5.0 | 18.2 | 23.0 | 38.0 | 196.7 | 100.9 | 14.3 | 3.8 | 30.1 | 42 |
| salary_min, month | 35 | 6,554 | 6,810 | 5,690 | 5,690 | 6,810 | 6,810 | 6,810 | 6,250 | 477 | -1.4 | -0.2 | 8 |

![salary](docs/figures/salary.png)

**posted_date (interval).** Median 2026-09-30, mean 2026-08-24, mode 2026-10-30, min 2017-11-30,
max 2026-11-05; IQR 70 days, std 138 days, skewness -7.5, kurtosis 85. 849 ads were posted before 2026.

#### What the measures show

| Finding | Goes to |
|---|---|
| Amazon is 39% of the ads (Apple 10.7%), software_internet 65%; CA and WA hold most ads | reduction (sampling) |
| `office_days` is 95.7% empty; seniority, work_mode, employment_type, degree, years 30-46% empty, because the ad does not say it (not MCAR) | cleaning: missing values |
| 15.3% of the ads have no salary, so they cannot train the model | cleaning: missing values |
| the salary mixes year, hour and month (25,903 / 1,178 / 37 rows) and USD, EUR, CAD; the mix shows at the low end (min 5, P5 51,400 against 8,625 and 70,350 for yearly) | cleaning (currency), integration (units) |
| yearly salary is skewed right (median 143,700 < mean 149,144, skewness 1.9) with heavy tails (kurtosis 7.6); the midrange is three times the median | transformation (log of the target) |
| not every outlier is wrong: the max ($890,000 - $1,690,000, Netflix) is stated in the ad; the min (8,625, Amazon) is a night-shift bonus | cleaning: outliers |
| `title` has 23,379 distinct values for 32,010 ads, with spelling variants; `role_family` has `other` as its mode | cleaning: noise |
| `seniority`: `lead` (19.2%) holds mostly managers ("Area Manager II"), so its place in the order is debatable | transformation (encoding) |

### 3. Data cleaning

Script `preprocessing/clean.py`: `data/intermediate/jobs.csv` (32,010 rows) → `data/intermediate/jobs_clean.csv`
(27,069 rows). The decisions follow the findings of Measuring data.

#### Missing values

Why a value is missing decides how it is handled:
- **MCAR** (missing completely at random): the gap has nothing to do with the data;
- **MAR** (at random): it depends on other columns, e.g. on the company's platform;
- **MNAR** (not at random): it depends on the value itself, e.g. the ad does not state it.

In this dataset an empty cell almost always means "the ad does not say it" (MNAR). For some columns it
also depends on the company: some platforms never give `work_mode` (MAR). So "not stated" is
information, and it is kept, not guessed.

Methods from the course, and the one used for each column:

| Column | Missing | Method | Why |
|---|---|---|---|
| salary (target) | 4,892 rows (15.3%) | **ignore the tuple** (drop the row) | without the target, a row cannot train the model |
| salary_max | 695 rows | **fill from the same row**: `salary_max = salary_min` | the ad says "from $X", a single amount |
| seniority, work_mode, employment_type, degree, states, cities | 4,255 to 12,620 rows | **global constant** `"unknown"` | MNAR / MAR: "not stated" is a category of its own |
| office_days | 95.7% | **drop the column** | too few values to use |
| detail_error | 100% | **drop the column** | no values |
| years_min, years_max, posted_date | 29.7%, 1.4% | **attribute median**, but later, at training | a median over all rows would include the test rows; imputers are fitted on the training set only |
| skills | 31.7% | none | not missing: the ad names none of the 43 skills, so every skill is 0 |

Not used: filling in by hand (thousands of rows), the class mean (the class is the salary we predict), the most
probable value from a model (more complex than needed for these columns).

#### Noisy data

Noise is a random error in a value. Here it comes from the extraction rules: an amount near a pay word
that is not the salary. The course methods are binning (smoothing by bin means, medians or boundaries),
regression, clustering, and **combined computer and human inspection**. The last one was used:
- the measures pointed to suspicious values (the min, the low percentiles, the currencies);
- each case was read by hand in `salary_text`;
- a rule removes the cases of that kind.

| Noise | Example | Rule | Rows dropped |
|---|---|---|---|
| salary in another currency | Cloudflare's Lisbon range in EUR; "AutoCAD" read as CAD | currency is not USD | 37 |
| an amount that is not pay | "Annual Recurring Revenue of $500K", "$5MM" projects, "$15k/month" compute funding | words: revenue, million, MM, funding for compute | 7 |
| below the US minimum wage | 8,625 a year: a night-shift bonus (Amazon) | < $7.25 an hour, < $15,080 a year (2,080 hours) | 2 |
| a typo read as an hourly rate | "MIN $167.00 - MAX $279,000.00" (Keysight) | hourly inferred from the amount and ≥ $100 | 3 |
| spelling variants in titles | "Sr." / "Senior", "–" / "-", double spaces | one form for spaces, dashes, Sr., Jr., Mgr | 0 (20,946 → 20,864 distinct titles) |

Binning was not used: smoothing the salary by bin means would replace every real salary with the mean
of its bin, and the target would lose exactly the detail the model has to learn.

#### Outliers

Outliers are values outside [Q1 - 1.5 IQR, Q3 + 1.5 IQR] (the whiskers of the boxplot), counted per pay
period because the units differ:

| Period | Outliers | Fences | Most of them |
|---|---|---|---|
| year | 1,045 of 25,865 | [15,750, 270,550] | Anthropic 365, OpenAI 217, Netflix 145 |
| hour | 39 of 1,169 | [0, 60] | Accenture 23 |
| month | 8 of 35 | [6,810, 6,810] | IQR = 0, the rule has no meaning here |

An outlier is not always an error. Above the fence are the real ranges of the AI labs and Netflix (max
$890,000 - $1,690,000, stated in the ad); removing them would teach the model that no job pays that
much. So outliers are **counted, not removed**. The wrong low values were already removed as noise, by
the minimum wage rule, not by IQR. The skewed salary is handled later (transformation: log of the target).

#### Result

| | Rows |
|---|---|
| read | 32,010 |
| no salary | -4,892 |
| wrong salaries (noise) | -49 |
| written | **27,069** |

### 4. Data integration

### 5. Data transformation

### 6. Data reduction

### 7. Data discretization


## Models to be run and comparison
