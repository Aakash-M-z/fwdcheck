"""Rank evidence by source type. Indian fact-checkers and official sources first."""
from urllib.parse import urlparse

# Dedicated fact-checking organisations (many are IFCN signatories)
FACT_CHECKERS = {
    "altnews.in", "boomlive.in", "factly.in", "newschecker.in", "vishvasnews.com",
    "factchecker.in", "newsmeter.in", "youturn.in", "factcrescendo.com",
    "logicallyfacts.com", "snopes.com", "fullfact.org", "politifact.com",
    "factcheck.afp.com", "dfrac.org",
}

# Paths that mark a fact-check section on a general news site
FACT_CHECK_PATH_HINTS = ("fact-check", "factcheck", "fact_check", "webqoof", "fake-news")

OFFICIAL_SUFFIXES = (".gov.in", ".nic.in", ".gov", "who.int", "un.org", "rbi.org.in",
                     "icmr.gov.in", "eci.gov.in")

NEWS_OUTLETS = {
    "thehindu.com", "indianexpress.com", "hindustantimes.com", "ndtv.com",
    "timesofindia.indiatimes.com", "indiatoday.in", "thequint.com", "livemint.com",
    "scroll.in", "theprint.in", "deccanherald.com", "news18.com", "bbc.com",
    "reuters.com", "apnews.com", "dinamani.com", "dailythanthi.com", "vikatan.com",
    "manoramaonline.com", "aajtak.in", "bhaskar.com", "economictimes.indiatimes.com",
}

LABELS = {
    "fact_checker": ("Fact-checker", 3.0),
    "official": ("Official", 3.0),
    "news": ("News outlet", 2.0),
    "other": ("Web", 1.0),
}


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _matches(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def classify(url: str) -> dict:
    host = _domain(url)
    path = urlparse(url).path.lower()
    if _matches(host, FACT_CHECKERS) or any(h in path for h in FACT_CHECK_PATH_HINTS):
        kind = "fact_checker"
    elif host.endswith(OFFICIAL_SUFFIXES) or host == "pib.gov.in":
        kind = "official"
    elif _matches(host, NEWS_OUTLETS):
        kind = "news"
    else:
        kind = "other"
    label, weight = LABELS[kind]
    return {"domain": host, "kind": kind, "kind_label": label, "weight": weight}


def rank_evidence(results: list[dict], limit: int = 8) -> list[dict]:
    """Deduplicate by URL, tag with source type, and sort by credibility."""
    seen, ranked = set(), []
    for pos, r in enumerate(results):
        link = r.get("link", "")
        if not link.startswith(("http://", "https://")) or link in seen:
            continue
        seen.add(link)
        info = classify(link)
        # credibility first, then original search position as a tie-breaker
        ranked.append({**r, **info, "_score": info["weight"] - pos * 0.01})
    ranked.sort(key=lambda x: x["_score"], reverse=True)
    for r in ranked:
        r.pop("_score", None)
    return ranked[:limit]
