"""One module per hiring platform (or per company with its own careers site).

Every reader has list_jobs(company) -> list of job dicts. If the list does not include the
description, the reader also has detail(company, job) -> the job with its description added.
A reader can set DETAIL_WORKERS (default 4) if the site blocks parallel requests.

A job dict always has: source_id, title, url, locations (list of strings), countries (ISO-2 codes).
It may also have: description (HTML or text), posted_at, and fields the platform states directly
(work_mode, employment_type, seniority, years_min, office_days, salary_*). Fields stated by the
platform are trusted; extract.py only fills in the ones that are missing.
"""

from . import (accenture, amazon, apple, ashby, atlassian, avature, eightfold, google, greenhouse, jibe, jsonld, lever,
               oraclecloud, phenom, radancy, smartrecruiters, workday)

ALL = {m.__name__.rsplit(".", 1)[-1]: m for m in (
    accenture, amazon, apple, ashby, atlassian, avature, eightfold, google, greenhouse, jibe, jsonld, lever,
    oraclecloud, phenom, radancy, smartrecruiters, workday)}
