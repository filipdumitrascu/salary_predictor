"""Step 1: collect the job ads of every company in companies.toml and save them unchanged.

Usage (from the repository root):
    python -m extraction.crawl                 # every company
    python -m extraction.crawl google stripe   # only these (slugs from companies.toml)
    python -m extraction.crawl --force         # read again companies that are already saved

Output: data/raw/<slug>.jsonl.gz, one job per line, as the company's hiring platform returned it
(title, description, locations, url, posting date...), plus the company slug and the collection time.
Nothing is extracted or cleaned here; that is extract.py's job, so the rules can change without
collecting again. A company that is already saved is skipped, so an interrupted run can be resumed.
Also writes data/raw/manifest.json: how many jobs each company had and when it was read.
"""

import argparse
import gzip
import json
import logging
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import readers

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
COMPANIES = Path(__file__).resolve().parent / "companies.toml"

log = logging.getLogger("crawl")


def load_companies() -> list[dict]:
    return tomllib.loads(COMPANIES.read_text(encoding="utf-8"))["company"]


def _with_detail(reader, company, job):
    """The job with its description. If the detail page fails, the listed job is kept (and marked)."""
    try:
        return reader.detail(company, job)
    except Exception as e:
        log.warning("%s: detail failed for %s: %s", company["slug"], job["source_id"], e)
        return {**job, "detail_error": str(e)[:200]}


def crawl(company: dict) -> list[dict]:
    reader = readers.ALL[company["platform"]]
    jobs = reader.list_jobs(company)
    if not jobs:
        raise RuntimeError("0 jobs listed: the reader is probably broken (site changed?)")
    log.info("%s: %d jobs listed", company["slug"], len(jobs))
    if hasattr(reader, "detail"):
        with ThreadPoolExecutor(getattr(reader, "DETAIL_WORKERS", 4)) as pool:
            jobs = list(pool.map(lambda j: _with_detail(reader, company, j), jobs))
    collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return [{"company": company["slug"], "collected_at": collected_at, **j} for j in jobs]


def save(slug: str, jobs: list[dict]) -> Path:
    path = RAW / f"{slug}.jsonl.gz"
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j, ensure_ascii=False, default=str) + "\n")  # default=str: dates as text
    tmp.replace(path)  # only a complete file gets the final name
    return path


def update_manifest(slug: str, entry: dict):
    path = RAW / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {}
    manifest[slug] = entry
    path.write_text(json.dumps(dict(sorted(manifest.items())), indent=2) + "\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slugs", nargs="*", help="companies to read (default: all)")
    parser.add_argument("--force", action="store_true", help="read again companies already saved")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    companies = load_companies()
    unknown = set(args.slugs) - {c["slug"] for c in companies}
    if unknown:
        parser.error(f"not in companies.toml: {', '.join(sorted(unknown))}")
    if args.slugs:
        companies = [c for c in companies if c["slug"] in args.slugs]

    RAW.mkdir(parents=True, exist_ok=True)
    failed = []
    for company in companies:
        slug = company["slug"]
        if (RAW / f"{slug}.jsonl.gz").exists() and not args.force:
            log.info("%s: already saved, skipped (use --force to read again)", slug)
            continue
        try:
            jobs = crawl(company)
        except Exception:
            log.exception("%s: failed", slug)
            failed.append(slug)
            continue
        save(slug, jobs)
        update_manifest(slug, {
            "name": company["name"], "platform": company["platform"], "jobs": len(jobs),
            "detail_errors": sum("detail_error" in j for j in jobs), "collected_at": jobs[0]["collected_at"],
        })
        log.info("%s: %d jobs saved", slug, len(jobs))

    if failed:
        log.error("failed: %s (run again with these slugs)", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
