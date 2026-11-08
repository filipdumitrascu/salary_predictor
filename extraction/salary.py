"""The salary stated in a job ad, read from its text with rules (regular expressions).

salary(text, country) returns a dict:
    min, max      the range; max is None for "from X" / "starts at X"
    currency      ISO code (USD, EUR, ...)
    period        "year", "month" or "hour"
    period_source "stated" (the text says per year / per hour ...) or "inferred" (guessed from the amount)
    text          the piece of the ad the salary was read from, to check the rules by hand
or None when no salary is found. Amounts are gross, in the ad's own currency.

How it works: find every amount with a currency ("$148,100", "120k EUR"), skip the ones that are not
pay (bonuses, company revenue, damages), keep the first one that has a pay word nearby ("salary",
"pay range", "compensation"...), then look right after it for the end of a range ("- $282,100").
"""

import re

CUR = r"(?:US\$|C\$|A\$|R\$|\$|€|£|₹|USD|EUR|GBP|RON|CHF|PLN|INR|CAD|AUD|SGD|lei)"
NUM = r"\d{1,3}(?:[.,  ]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
AMOUNT = re.compile(rf"(?P<c1>{CUR})\s?(?P<n1>{NUM})(?P<k1>\s?[kK]\b)?|(?P<n2>{NUM})(?P<k2>\s?[kK]\b)?\s?(?P<c2>{CUR})(?![a-z])")
# The end of a range: "- $185,000", "to 71,500", "/year in our lowest market up to $185,000/year" (Amazon)
SECOND = re.compile(
    rf"\s*(?:\((?:USD|EUR|CAD)\))?(?:/\s*[a-z]+)?[^\d$€£\n]{{0,70}}?(?:-|–|—|\bto\b|\bbis\b|până la|\bși\b|\bsi\b|\band\b|\bund\b)\s*(?:{CUR}\s?)?(?P<n>{NUM})(?P<k>\s?[kK]\b)?",
    re.I,
)
FIRST = re.compile(rf"(?P<n>{NUM})(?P<k>\s?[kK])?\s*(?:-|–|—|\bto\b|până la)\s*$", re.I)  # "8000 - " before "12000 RON"
PAY_WORDS = re.compile(r"sal[aá]r|\bpay\b|compensation|wage|remunerat|stipend|allowance|gehalt|vergütung|brutto|gross|base|range|annual", re.I)
# "$307,000 - $427,000 + 30% bonus": bonus/equity right AFTER an amount mean it is the base pay.
PAY_WORDS_AFTER = re.compile(PAY_WORDS.pattern + r"|bonus|equity", re.I)
NOT_SALARY = re.compile(r"\s*(?:billion|million|bn\b|[BM]\b|in damages|(?:usd\s*)?(?:sign|signing|bonus|relocation|referral))", re.I)
BONUS_BEFORE = re.compile(r"(?:sign[- ]?on|signing|bonus|relocation|referral|retention|stipend for|allowance of)[^.\d]{0,80}$", re.I)
SYMBOL = {"R$": "BRL", "US$": "USD", "C$": "CAD", "A$": "AUD", "€": "EUR", "£": "GBP", "₹": "INR", "lei": "RON"}
DOLLAR = {"CA": "CAD", "AU": "AUD", "SG": "SGD", "NZ": "NZD", "MX": "MXN", "HK": "HKD"}  # what "$" means in these countries
PLAUSIBLE = {"year": (5_000, 2_000_000), "month": (300, 100_000), "hour": (5, 1_000)}

# When the ad does not say the period, it is guessed from the amount only where the guess is safe:
# 25,000 or more is a yearly salary, under 200 is an hourly wage. Amounts in between (e.g. 580, 8,625)
# could be a monthly salary, a bonus or something else, so they are skipped rather than guessed.
# Exception: Romanian ads (lei/RON) state monthly gross pay, so lei amounts default to monthly.
YEARLY_FROM, HOURLY_UNDER = 25_000, 200


def _number(s: str, k: str | None) -> float:
    s = s.replace(" ", "").replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?", s):  # 141,000 / 2.800 / 141,000.00
        whole, _, dec = re.match(r"(.*?)(?:([.,])(\d{1,2}))?$", s).groups()
        value = float(re.sub(r"[.,]", "", whole) + ("." + dec if dec else ""))
    else:  # 21.50 / 1116,90 / 307000
        value = float(s.replace(",", "."))
    return value * 1000 if k else value


def _stated_period(window: str) -> str | None:
    w = window.lower()
    if re.search(r"/\s*h(ou)?r\b|per hour|hourly|an hour|pro stunde", w):
        return "hour"
    if re.search(r"/\s*mo(nth)?\b|per month|monthly|a month|pro monat|/monat|lunar|pe lun|por m[eê]s|al mes|mensal", w):
        return "month"
    if re.search(r"/\s*y(ea)?r\b|per year|annual|a year|yearly|pro jahr|jährlich|per annum|pe an|por ano|al año|anual", w):
        return "year"
    return None


def _inferred_period(value: float, lei: bool) -> str | None:
    if lei:
        return "hour" if value < 100 else "month" if value < 100_000 else "year"
    if value < HOURLY_UNDER:
        return "hour"
    if value >= YEARLY_FROM:
        return "year"
    return None


def _currency(symbol: str, window: str, country: str | None) -> str:
    code = re.search(r"\b(USD|CAD|AUD|EUR|GBP|CHF|SGD)\b", window)
    if symbol == "$":
        return code.group(1) if code else DOLLAR.get(country or "", "USD")
    return SYMBOL.get(symbol, symbol.upper())


def salary(text: str, country: str | None = None) -> dict | None:
    text = text or ""
    for m in AMOUNT.finditer(text):
        if NOT_SALARY.match(text, m.end()) or BONUS_BEFORE.search(text, max(0, m.start() - 100), m.start()):
            continue
        before, after = text[max(0, m.start() - 250): m.start()], text[m.end(): m.end() + 40]
        if not (PAY_WORDS.search(before) or PAY_WORDS_AFTER.search(after)):
            continue
        low = _number(m.group("n1") or m.group("n2"), m.group("k1") or m.group("k2"))
        high, start, end = None, m.start(), m.end()
        first = FIRST.search(text[max(0, m.start() - 30): m.start()]) if m.group("n2") else None
        r = SECOND.match(text, m.end())
        if first and (prev := _number(first.group("n"), first.group("k") or m.group("k2"))) < low <= 4 * prev:
            low, high, start = prev, low, m.start() - len(first.group(0))
        elif r:
            second = _number(r.group("n"), r.group("k") or (m.group("k1") or m.group("k2")))
            if low <= second <= 4 * low:  # "$95,000 - $95,000" is a range too
                high, end = second, r.end()
        window = text[max(0, start - 70): end + 60]
        symbol = m.group("c1") or m.group("c2")
        period, source = _stated_period(window), "stated"
        if period is None:
            period, source = _inferred_period(low, lei=symbol.lower() in ("lei", "ron")), "inferred"
        if period is None:
            continue
        lo, hi = PLAUSIBLE[period]
        if not lo <= low <= hi:
            continue
        snippet = re.sub(r"\s+", " ", text[max(0, start - 80): end + 40]).strip()
        return {"min": low, "max": high, "currency": _currency(symbol, window, country),
                "period": period, "period_source": source, "text": snippet}
    return None
