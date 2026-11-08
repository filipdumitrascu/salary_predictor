"""HTTP for the readers: one shared session, a pause between requests, retries on temporary errors."""

import threading
import time

import requests

USER_AGENT = "Mozilla/5.0 (compatible; salary-predictor/1.0; university data-collection project)"
DELAY = 0.25  # seconds between two requests (over all threads): at most ~4 requests per second
TIMEOUT = 30

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

_lock = threading.Lock()
_last = 0.0


def _wait_turn():
    global _last
    with _lock:
        pause = _last + DELAY - time.monotonic()
        if pause > 0:
            time.sleep(pause)
        _last = time.monotonic()


def request(method: str, url: str, **kw) -> requests.Response:
    """HTTP with 3 attempts on network errors, 429 (too many requests) and 5xx. Raises on final failure."""
    for attempt in range(3):
        _wait_turn()
        try:
            r = session.request(method, url, timeout=TIMEOUT, **kw)
            if r.status_code != 429 and r.status_code < 500:
                r.raise_for_status()
                return r
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
        time.sleep(2 ** (attempt + 1))  # 2 s, 4 s, 8 s
    r.raise_for_status()
    return r


def get_json(url: str, **kw):
    return request("GET", url, **kw).json()


def post_json(url: str, body: dict):
    return request("POST", url, json=body).json()
