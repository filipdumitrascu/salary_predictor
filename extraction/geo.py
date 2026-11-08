"""Country, city and US state from free-text locations.

Careers sites write locations in many forms: "Seattle, WA, USA", "US, California, Santa Clara",
"Virginia - Mclean", "Austin, United States", "Hyderabad, TS, IN". The rules below read all of them.
"""

import re
import unicodedata

COUNTRY_NAMES = {
    "romania": "RO", "germany": "DE", "deutschland": "DE", "france": "FR", "spain": "ES", "portugal": "PT", "italy": "IT",
    "netherlands": "NL", "belgium": "BE", "luxembourg": "LU", "ireland": "IE", "united kingdom": "GB", "uk": "GB",
    "england": "GB", "scotland": "GB", "switzerland": "CH", "austria": "AT",
    "poland": "PL", "czech republic": "CZ", "czechia": "CZ", "slovakia": "SK", "hungary": "HU", "bulgaria": "BG",
    "serbia": "RS", "croatia": "HR", "slovenia": "SI", "greece": "GR", "cyprus": "CY", "malta": "MT",
    "moldova": "MD", "ukraine": "UA", "lithuania": "LT", "latvia": "LV", "estonia": "EE", "finland": "FI",
    "sweden": "SE", "norway": "NO", "denmark": "DK", "iceland": "IS", "turkey": "TR", "türkiye": "TR", "turkiye": "TR", "israel": "IL",
    "united states": "US", "united states of america": "US", "usa": "US", "us": "US", "canada": "CA", "mexico": "MX", "brazil": "BR",
    "argentina": "AR", "chile": "CL", "colombia": "CO", "india": "IN", "china": "CN", "japan": "JP",
    "south korea": "KR", "korea": "KR", "australia": "AU", "new zealand": "NZ",
    "united arab emirates": "AE", "uae": "AE", "saudi arabia": "SA", "south africa": "ZA",
    "egypt": "EG", "nigeria": "NG", "kenya": "KE", "indonesia": "ID", "malaysia": "MY", "philippines": "PH",
    "thailand": "TH", "vietnam": "VN", "viet nam": "VN", "taiwan": "TW", "costa rica": "CR", "singapore": "SG",
    # "georgia" left out on purpose: it is also a US state
    "armenia": "AM", "azerbaijan": "AZ", "belarus": "BY", "kazakhstan": "KZ", "montenegro": "ME",
    "north macedonia": "MK", "albania": "AL", "bosnia and herzegovina": "BA", "qatar": "QA",
    "ecuador": "EC", "peru": "PE", "uruguay": "UY", "pakistan": "PK", "sri lanka": "LK",
}
CITY_HINTS = {  # cities that name their country when the location does not
    "bucharest": "RO", "cluj": "RO", "london": "GB", "dublin": "IE", "dubai": "AE", "hong kong": "HK",
    "toronto": "CA", "vancouver": "CA", "paris": "FR", "berlin": "DE", "munich": "DE", "amsterdam": "NL", "madrid": "ES",
    "barcelona": "ES", "warsaw": "PL", "tokyo": "JP", "bengaluru": "IN", "bangalore": "IN", "hyderabad": "IN",
    "sydney": "AU", "melbourne": "AU", "zurich": "CH", "stockholm": "SE", "vienna": "AT", "milan": "IT", "prague": "CZ",
    "new york": "US", "nyc": "US", "san francisco": "US", "seattle": "US", "chicago": "US", "atlanta": "US",
}
COUNTRIES = {**COUNTRY_NAMES, **CITY_HINTS}
_COUNTRY = re.compile(r"\b(" + "|".join(sorted(map(re.escape, COUNTRIES), key=len, reverse=True)) + r")\b", re.I)

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}
STATE_BY_NAME = {name.lower(): code for code, name in US_STATES.items()} | {"washington dc": "DC", "washington d.c.": "DC"}

# Large US cities with ONE well-known state, for locations that give no state ("Austin, United States").
# Cities whose name exists in several states with real job markets are left out on purpose
# (Arlington VA/TX, Columbus OH/GA, Portland OR/ME, Cambridge MA, Kansas City MO/KS, Springfield...).
US_CITY_STATE = {
    "seattle": "WA", "redmond": "WA", "bellevue": "WA", "kirkland": "WA", "tacoma": "WA", "spokane": "WA",
    "san francisco": "CA", "san jose": "CA", "santa clara": "CA", "sunnyvale": "CA", "mountain view": "CA",
    "palo alto": "CA", "menlo park": "CA", "cupertino": "CA", "milpitas": "CA", "fremont": "CA", "oakland": "CA",
    "san mateo": "CA", "redwood city": "CA", "south san francisco": "CA", "east palo alto": "CA", "los gatos": "CA",
    "los angeles": "CA", "culver city": "CA", "santa monica": "CA", "irvine": "CA", "san diego": "CA",
    "sacramento": "CA", "folsom": "CA", "santa rosa": "CA", "santa barbara": "CA",
    "new york": "NY", "brooklyn": "NY", "austin": "TX", "dallas": "TX", "houston": "TX", "irving": "TX",
    "plano": "TX", "san antonio": "TX", "boston": "MA", "chicago": "IL", "atlanta": "GA", "denver": "CO",
    "boulder": "CO", "phoenix": "AZ", "tempe": "AZ", "chandler": "AZ", "scottsdale": "AZ", "nashville": "TN",
    "herndon": "VA", "mclean": "VA", "reston": "VA", "pittsburgh": "PA", "philadelphia": "PA", "hillsboro": "OR",
    "raleigh": "NC", "durham": "NC", "charlotte": "NC", "detroit": "MI", "minneapolis": "MN",
    "salt lake city": "UT", "miami": "FL", "orlando": "FL", "tampa": "FL", "las vegas": "NV", "baltimore": "MD",
    "washington dc metro": "DC", "washington, dc": "DC",
}

CITY_ALIASES = {"bucuresti": "Bucharest", "cluj": "Cluj-Napoca", "munchen": "Munich", "bangalore": "Bengaluru",
                "nyc": "New York", "new york city": "New York", "sf": "San Francisco"}
# Regions that some sites write before the city ("US, Oregon, Hillsboro"): never a city themselves.
# "New York" is left out: it is far more often the city than the state.
REGIONS = {s.lower() for s in US_STATES.values()} - {"new york"} | {
    "karnataka", "telangana", "maharashtra", "tamil nadu", "uttar pradesh", "haryana",
    "ontario", "quebec", "british columbia", "alberta", "bavaria", "bayern", "england", "scotland", "wales"}
NOT_A_CITY = re.compile(r"remote|multiple|anywhere|various|hybrid|virtual|location|headquarters|^n/?a$", re.I)


def _plain(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _parts(location: str) -> list[str]:
    return [p.strip() for chunk in location.split(" - ") for p in chunk.split(",") if p.strip()]


def countries_in(text: str) -> list[str]:
    """ISO-2 codes of every country named in a free-text location, in order, no duplicates."""
    return list(dict.fromkeys(COUNTRIES[m.lower()] for m in _COUNTRY.findall(text or "")))


def city_of(location: str) -> str | None:
    """'Iași, IS, Romania' -> 'Iasi'; None when the location names no city ('Remote', 'Romania', 'RO')."""
    # The city is the first part that isn't a country, a region or a code: "USA - Sunnyvale, CA",
    # "United Kingdom, Edinburgh, SC". Digits mean a building or street, not a city.
    name = next((p for p in _parts(location) if p.lower() not in COUNTRY_NAMES and p.lower() not in REGIONS
                 and not re.fullmatch(r"[A-Z]{2}", p)), None)
    if not name or NOT_A_CITY.search(name) or re.search(r"\d", name):
        return None
    name = _plain(name)
    if name.isupper():  # "HYDERABAD"
        name = name.title()
    return CITY_ALIASES.get(name.lower(), name)


def us_state(location: str, job_countries: list[str] = ()) -> str | None:
    """Two-letter US state of a location, or None if it is not in the US or the state cannot be told.

    Two-letter codes are the tricky part: in "Hyderabad, TS, IN" the "IN" is India, not Indiana, and
    in "Toronto, ON, CA" the "CA" is Canada, not California. So a code that is the last part of the
    location and is one of the job's non-US countries is read as that country.
    """
    if any(c != "US" for c in countries_in(location)) and "US" not in countries_in(location):
        return None  # names another country
    parts = _parts(location)
    if len(parts) >= 3 and re.fullmatch(r"[A-Z]{2}", parts[-1]) and parts[-1] != "US":
        return None  # "Chennai, TN, IN": city, region, country code; TN is not Tennessee here
    if any(p.upper().replace(".", "") == "DC" for p in parts):
        return "DC"  # before "Washington", which is also a state
    for p in parts:  # full state names: "US, California, Santa Clara", "Virginia - Mclean"
        if p.lower() in STATE_BY_NAME and not (p.lower() == "new york" and p is parts[0] and len(parts) > 1):
            return STATE_BY_NAME[p.lower()]
    for i, p in enumerate(parts):  # codes: "Seattle, WA, USA", "Austin, TX"
        if p in US_STATES and (i > 0 or "US" in countries_in(location) or list(job_countries) == ["US"]):
            is_last = i == len(parts) - 1
            if is_last and p in job_countries and p != "US" and "US" not in job_countries:
                return None  # "..., CA" is Canada here
            return p
    if "US" in countries_in(location) or list(job_countries) == ["US"]:
        city = city_of(location)
        return US_CITY_STATE.get(city.lower()) if city else None
    return None


def place(location: str, job_countries: list[str]) -> dict:
    """{'country', 'state', 'city'} of one location string; unknown parts are None."""
    state = us_state(location, job_countries)
    named = countries_in(location)
    if state:
        country = "US"
    elif named:
        country = named[0]
    else:
        code = location.rsplit(",", 1)[-1].strip()  # "Hyderabad, TS, IN" ends with the country code
        country = code if code in job_countries else (job_countries[0] if len(job_countries) == 1 else None)
    city = city_of(location)
    if state == "DC" and not city:
        city = "Washington"
    return {"country": country, "state": state, "city": city}
