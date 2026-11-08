"""Rule-based extraction of the job's fields from its title and description.

normalize(job) takes a raw job (as a reader returns it) and returns the extracted fields.
Fields the platform already states (job["seniority"], job["work_mode"]...) are kept as they are;
rules only fill what is still missing. None means "unknown": better than a wrong guess.
"""

import html
import re

from .salary import salary


def html_to_text(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"(?i)<(br|/p|/li|/h\d|/div|/tr)\b[^>]*>", "\n", s)
    s = re.sub(r"(?i)<li\b[^>]*>", "\n• ", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n\n", s).strip()


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.I) is not None


def _first(rules: list[tuple[str, str]], text: str) -> str | None:
    return next((value for value, pattern in rules if _has(pattern, text)), None)


# Matched against the title. Order matters: the first match wins.
SENIORITY = [
    ("intern", r"\b(intern|interns|internship|trainee|working student|werkstudent|praktikum|stagiar|stagiaire|apprentice)\b|^stage\b"),  # \b: not "International"
    ("director", r"\b(director|vice president|vp|head of|chief|cto|cio|ciso)\b"),
    ("staff", r"\b(staff|principal|distinguished|fellow)\b"),
    ("lead", r"\blead\b|(?<!product )(?<!program )(?<!project )(?<!account )(?<!marketing )(?<!sales )\bmanager\b"),
    ("senior", r"\b(senior|sr|iii|iv)\b"),
    ("entry", r"\b(junior|jr|entry[- ]level|entry|graduate|new grad|early career)\b|\bi$"),
    ("mid", r"\b(mid|ii|intermediate)\b"),
]

# Matched against the title. Order matters: "Embedded Software Engineer" is hardware, not software.
ROLE_FAMILY = [
    ("security", r"secur|cyber|penetration|threat|malware|vulnerab"),
    ("hardware", r"embedded|firmware|hardware|asic|fpga|silicon|verification engineer|\bchip|analog|\brf\b|layout engineer|pcb|electronic|semiconductor|mixed[- ]signal|validation engineer"),
    ("data", r"data scien|machine learning|\bml\b|\bai\b|deep learning|data engineer|data analyst|analytics|research scientist|applied scientist|\bnlp\b|computer vision|business intelligence|\bbi\b"),
    ("devops", r"devops|\bsre\b|site reliability|cloud engineer|infrastructure|platform engineer|network engineer|systems engineer|kubernetes"),
    ("qa", r"\bqa\b|quality assurance|\btest(er|ing)?\b|sdet|automation engineer"),
    ("product", r"product manager|product owner|product management"),
    ("design", r"designer|\bux\b|\bui\b|user experience|user research"),
    ("software", r"software|developer|programmer|\bsde\b|\bswe\b|backend|back-end|frontend|front-end|full[- ]?stack|\bdev\b|\bios\b|android|mobile engineer|web engineer"),
    ("program", r"program manager|project manager|scrum master|delivery manager"),
    ("engineering", r"engineer|engineering|architect"),  # other engineering (mechanical, solutions, ...)
    ("support", r"support|helpdesk|service desk|technician"),
    ("sales", r"sales|account (executive|manager)|business development|customer success"),
    ("marketing", r"marketing|brand|content|communications|\bseo\b|growth"),
    ("people", r"\bhr\b|human resources|recruit|talent|people partner|total rewards"),
    ("finance", r"financ|accountant|accounting|controller|audit|\btax\b|treasury|payroll"),
    ("legal", r"legal|counsel|lawyer|compliance|privacy"),
    ("operations", r"operations|logistic|supply chain|warehouse|procurement|fulfillment"),
]

DEGREE = [  # lowest first: the minimum degree the ad asks for
    ("bachelor", r"bachelor|\bb\.?sc\b|\bbs\b(?=\s*(/|or\b|in\b|degree))|\bb\.?eng\b|undergraduate degree|university degree|licen[tț][aăi]"),
    ("master", r"master'?s\b|\bm\.?sc\b|\bms\b(?=\s*(/|or\b|in\b|degree))|\bmba\b|\bm\.?eng\b"),
    ("phd", r"\bph\.?d|doctorate|doctoral"),
]

# Title and location patterns are loose; description patterns must be explicit ("hybrid cloud" is not a work mode).
MODE_TITLE = [("hybrid", r"\bhybrid\b"), ("remote", r"\bremote\b"), ("onsite", r"on[- ]?site")]
MODE_TEXT = [
    ("hybrid", r"hybrid\s*(work|role|position|working|schedule|arrangement|model|setup|policy)|\(hybrid\)|work(ing)? (in )?(a )?hybrid"),
    ("remote", r"fully remote|100% remote|remote[- ]first|\(remote\)|remote (role|position)|work from home"),
    ("onsite", r"fully on[- ]?site|on[- ]?site (role|position)|office[- ]based|5 days (a|per) week in the office"),
]

TYPE_TITLE = [
    ("part-time", r"part[- ]time"),
    ("contract", r"\b(contract|contractor|fixed[- ]term|temporary)\b"),
    ("full-time", r"full[- ]time"),
]
TYPE_TEXT = [("part-time", r"part[- ]time (role|position|job)"), ("contract", r"fixed[- ]term contract"), ("full-time", r"full[- ]time")]

YEARS = re.compile(r"(?<!\d)(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*(\d{1,2})\s*)?\+?\s*years?", re.I)
OFFICE_DAYS = re.compile(r"(\d)\s*(?:days?|x)\s*(?:a|per|/|each)?\s*week\s*(?:in|at|from)?\s*(?:the\s*|our\s*)?(?:office|on[- ]?site|in-office)", re.I)

SKILL_WORDS = {  # looked up in the description's words, in one pass
    "Python": {"python"}, "Java": {"java"}, "JavaScript": {"javascript"}, "TypeScript": {"typescript"}, "C++": {"c++"},
    "C#": {"c#"}, "Go": {"golang"}, "Rust": set(), "Kotlin": {"kotlin"}, "Swift": set(), "Scala": {"scala"},
    "PHP": {"php"}, "SQL": {"sql"}, "React": {"react", "react.js", "reactjs"}, "Angular": {"angular", "angularjs"},
    "Vue": {"vue", "vue.js", "vuejs"}, "Node.js": {"node.js", "nodejs"}, ".NET": set(), "Spring": {"spring"},
    "AWS": {"aws"}, "Azure": {"azure"}, "GCP": {"gcp"}, "Kubernetes": {"kubernetes", "k8s"}, "Docker": {"docker"},
    "Terraform": {"terraform"}, "Linux": {"linux"}, "Spark": {"spark", "pyspark"}, "Kafka": {"kafka"},
    "PyTorch": {"pytorch"}, "TensorFlow": {"tensorflow"}, "Machine Learning": {"ml"}, "LLM": {"llm", "llms", "genai"},
    "Verilog": {"verilog", "systemverilog"}, "VHDL": {"vhdl"}, "FPGA": {"fpga", "fpgas"}, "Embedded": {"embedded"},
    "MATLAB": {"matlab"}, "Power BI": {"powerbi"}, "Tableau": {"tableau"}, "SAP": set(), "Salesforce": {"salesforce"},
    "Git": {"git"}, "CI/CD": {"ci/cd"},
}
SKILL_PHRASES = {"Machine Learning": ["machine learning"], "LLM": ["large language model", "generative ai"],
                 ".NET": [".net"], "GCP": ["google cloud"], "AWS": ["amazon web services"], "Power BI": ["power bi"]}
SKILL_CASED = {name: re.compile(p) for name, p in {  # words that are also common English: only with their exact case
    "Go": r"\bGo\b(?=\s*(?:,|/|\)|and\b|or\b|lang))", "Rust": r"\bRust\b", "Swift": r"\bSwift\b", "SAP": r"\bSAP\b"}.items()}
TOKEN = re.compile(r"[a-z0-9+#]+(?:[./][a-z0-9+#]+)*")


def years_required(text: str) -> tuple[int | None, int | None]:
    """(smallest, largest) number of years of experience the ad mentions; (None, None) if none.

    An ad often mentions several: "5+ years of C++ experience ... 2 years of Linux experience".
    Both ends are kept; which one predicts pay better is decided later, on the data.
    """
    found = [
        int(n)
        for m in YEARS.finditer(text)
        for n in filter(None, m.groups())  # "3-5 years" gives both 3 and 5
        if int(m.group(1)) <= 20 and _has(r"experience|\bexp\b|working|industry", text[m.end(): m.end() + 60])
        and not _has(r"^\s*(of age|old|or older)", text[m.end(): m.end() + 15])  # "18 years of age" is not experience
    ]
    return (min(found), max(found)) if found else (None, None)


def office_days(text: str) -> int | None:
    m = OFFICE_DAYS.search(text)
    return int(m.group(1)) if m and int(m.group(1)) <= 5 else None


def skills(text: str) -> list[str]:
    lower = text.lower()
    tokens = set()
    for t in TOKEN.findall(lower):
        tokens.add(t)
        tokens.update(t.split("/"))  # "java/kotlin" -> java, kotlin
    return [
        name for name, words in SKILL_WORDS.items()
        if words & tokens or any(p in lower for p in SKILL_PHRASES.get(name, ())) or (name in SKILL_CASED and SKILL_CASED[name].search(text))
    ]


def normalize(job: dict, country: str | None = None) -> dict:
    """The extracted fields of one raw job. `country` (ISO-2) tells what "$" means (USD, CAD...)."""
    title = re.sub(r"\s+", " ", job["title"]).strip()
    text = html_to_text(job.get("description"))
    head = text[:3000]  # work mode and contract type are usually stated early

    y_min, y_max = years_required(text)
    if job.get("years_min") is not None:  # stated by the platform (Accenture)
        y_min, y_max = job["years_min"], max(job["years_min"], y_max or 0)

    if job.get("seniority"):
        seniority, seniority_source = job["seniority"], "platform"
    elif level := _first(SENIORITY, title):
        seniority, seniority_source = level, "title"
    else:
        seniority, seniority_source = None, None

    days = job.get("office_days")
    if days is None:
        days = office_days(text)
    if days is not None:  # stated office days beat any label (Microsoft labels "2 days/week" jobs as onsite)
        mode = "remote" if days == 0 else "onsite" if days == 5 else "hybrid"
    else:
        where = title + " | " + " | ".join(job.get("locations") or [])  # "Poland - Remote" is in the location
        mode = job.get("work_mode") or _first(MODE_TITLE, where) or _first(MODE_TEXT, head)

    pay = salary(text, country) or {}
    return {
        "title": title,
        "seniority": seniority,
        "seniority_source": seniority_source,
        "role_family": job.get("role_family") or _first(ROLE_FAMILY, title) or "other",
        "years_min": y_min,
        "years_max": y_max,
        "degree": job.get("degree") or _first(DEGREE, text),
        "skills": skills(title + "\n" + text),
        "work_mode": mode,
        "office_days": days,
        "employment_type": job.get("employment_type") or _first(TYPE_TITLE, title) or _first(TYPE_TEXT, head),
        "salary_min": pay.get("min"),
        "salary_max": pay.get("max"),
        "salary_currency": pay.get("currency"),
        "salary_period": pay.get("period"),
        "salary_period_source": pay.get("period_source"),
        "salary_text": pay.get("text"),
        "description_chars": len(text),
    }
