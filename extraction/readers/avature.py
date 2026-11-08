"""Avature careers sites (Siemens, Lenovo, Electronic Arts...): server-rendered HTML.
Config: base (site URL up to the portal, e.g. https://jobs.lenovo.com/en_US/careers)."""

import html
import re

from ..fetch import request
from ..geo import countries_in

FIELD = re.compile(r'article__content__view__field__label[^>]*>(.*?)</div>\s*<div[^>]*article__content__view__field__value[^>]*>(.*?)</div>\s*</div>', re.S)


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def list_jobs(c):
    # only the site's own job links (pages also carry "share by email/LinkedIn" links to the same jobs)
    link = re.compile(rf'<a[^>]+href="({re.escape(c["base"])}/JobDetail/[^"]*?(\d+))"[^>]*>(.*?)</a>', re.S)
    jobs, offset = {}, 0
    while offset < 20000:
        page = request("GET", f"{c['base']}/SearchJobs/", params={"jobOffset": offset}).text
        found = {}
        for url, jid, title in link.findall(page):  # the first link to a job carries its title; later ones say "Apply"
            if _text(title) and jid not in found:
                found[jid] = (url, _text(title))
        new = {jid: v for jid, v in found.items() if jid not in jobs}
        if not new:
            break
        jobs.update((jid, {"source_id": jid, "url": html.unescape(url), "title": title}) for jid, (url, title) in new.items())
        offset += len(found)
    return list(jobs.values())


def _pick(value: str, options: dict) -> str | None:
    return next((v for k, v in options.items() if k in value.lower()), None)


def detail(c, job):
    page = request("GET", job["url"]).text
    fields = {_text(label).lower().rstrip(":"): value for label, value in FIELD.findall(page)}
    get = lambda *names: next((_text(v) for k, v in fields.items() if any(n in k for n in names)), "")
    # "Location(s)" lists (Siemens) or separate City / State / Country fields (Lenovo)
    locs = [_text(li) for k, v in fields.items() if "location" in k for li in re.findall(r"<li[^>]*>(.*?)</li>", v, re.S) or [v]]
    if not locs and get("city", "country"):
        locs = [", ".join(filter(None, [get("city"), get("state"), get("country")]))]
    if not locs:  # EA: <div class="... field--locations"><div ...value"><strong>Locations</strong>: A<br>B
        block = re.search(r'field--locations[^>]*>\s*<div[^>]*field__value[^>]*>(.*?)</div>', page, re.S)
        if block:
            locs = [re.sub(r"^Locations?\s*:\s*", "", _text(part)) for part in re.split(r"<br\s*/?>", block.group(1))]
    locs = [loc for loc in locs if loc]
    # the description is the long unlabeled text; field names differ per site
    texts = re.findall(r'class="article__content__view__field__value">(.*?)</div>\s*</div>', page, re.S)
    return {
        **job,
        "locations": locs,
        "countries": countries_in(" | ".join(locs)),
        "description": " ".join(t for t in texts if len(_text(t)) > 200),
        "work_mode": _pick(get("work mode", "work model"), {"hybrid": "hybrid", "remote": "remote", "office": "onsite", "on-site": "onsite", "onsite": "onsite"}),
        "employment_type": _pick(get("job type", "working time", "worker type"), {"part": "part-time", "temporary": "contract", "contract": "contract", "full": "full-time"}),
    }
