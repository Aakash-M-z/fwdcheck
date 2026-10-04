"""The fact-checking pipeline.

1. Extract checkable claims from the forward (any Indian language).
2. For each claim, gather live evidence with SerpApi:
     - Google web search for "<claim> fact check"
     - Google News search for the claim
     - Google search in the forward's own language (if not English)
3. Rank evidence (fact-checkers and official sources first).
4. Ask the LLM for a verdict that may ONLY cite the retrieved evidence.
5. Write a short, polite reply the user can paste back into the group.
"""
import time
from concurrent.futures import ThreadPoolExecutor

from llm import chat_json
from serp import SerpClient
from sources import rank_evidence

MAX_CLAIMS = 3
VERDICTS = {"true", "false", "misleading", "unverified"}

EXTRACT_SYSTEM = """You extract checkable factual claims from WhatsApp/social media forwards
circulating in India. The forward may be in English, Tamil, Hindi, or any Indian language,
or mixed (e.g. Tanglish, Hinglish).

Return JSON:
{
  "language_code": "ISO 639-1 code of the forward's main language, e.g. en, ta, hi",
  "language_name": "e.g. Tamil",
  "claims": [
    {
      "claim": "the claim, restated clearly in English",
      "search_query": "short English Google query (max 8 words) to verify it",
      "native_query": "same query in the forward's language, or empty string if English"
    }
  ]
}
Rules: at most {max} claims, most important first. Skip opinions, greetings, and
calls to "forward this to 10 people". If there is nothing checkable, return an empty list."""

JUDGE_SYSTEM = """You are a careful fact-checker. Judge ONE claim using ONLY the numbered
evidence provided (live search results). Never use outside knowledge to invent facts.

Verdicts:
- "false": credible evidence contradicts the claim (e.g. a fact-checker debunked it)
- "true": credible evidence clearly supports it
- "misleading": partly true but missing context, outdated, or exaggerated
- "unverified": evidence is missing, weak, or conflicting

Weigh fact-checkers and official sources above other websites.

Return JSON:
{
  "verdict": "true | false | misleading | unverified",
  "confidence": 0-100,
  "explanation": "2-3 plain English sentences explaining why, mentioning sources by name",
  "cited": [list of evidence numbers you relied on]
}"""

REPLY_SYSTEM = """Write a short, friendly reply someone can paste into a family or friends
WhatsApp group to correct or confirm a forward. Be respectful, never mocking.
Max 60 words. Write it in {language}. Include at most 2 source links from the list.
Return JSON: {{"reply": "..."}}"""


def extract_claims(text: str) -> dict:
    data = chat_json(EXTRACT_SYSTEM.replace("{max}", str(MAX_CLAIMS)), text)
    data["claims"] = [c for c in data.get("claims", []) if c.get("claim")][:MAX_CLAIMS]
    return data


def gather_evidence(serp: SerpClient, claim: dict, lang: str) -> tuple[list, list]:
    """Run SerpApi searches for one claim. Returns (ranked_evidence, trace)."""
    q = claim.get("search_query") or claim["claim"]
    jobs = [
        ("google", f"{q} fact check", "en", serp.web),
        ("google_news", q, "en", serp.news),
    ]
    native = (claim.get("native_query") or "").strip()
    if native and lang != "en":
        jobs.append(("google", native, lang, serp.web))

    results, trace = [], []
    for engine, query, hl, fn in jobs:
        t0 = time.time()
        try:
            found, cached = fn(query, hl=hl)
            error = None
        except Exception as exc:  # one failed search shouldn't kill the whole check
            found, cached, error = [], False, str(exc)
        results.extend(found)
        trace.append({"engine": engine, "query": query, "hl": hl, "results": len(found),
                      "cached": cached, "ms": int((time.time() - t0) * 1000),
                      "error": error})
    return rank_evidence(results), trace


def judge_claim(claim: dict, evidence: list) -> dict:
    if not evidence:
        return {"verdict": "unverified", "confidence": 0, "cited": [],
                "explanation": "No search results were found for this claim, so it "
                               "could not be verified. Treat it with caution."}
    lines = []
    for i, e in enumerate(evidence, 1):
        lines.append(f"[{i}] ({e['kind_label']}) {e['source'] or e['domain']} | "
                     f"{e['date']}\nTitle: {e['title']}\nSnippet: {e['snippet']}")
    user = f"CLAIM: {claim['claim']}\n\nEVIDENCE:\n" + "\n\n".join(lines)
    result = chat_json(JUDGE_SYSTEM, user)

    verdict = str(result.get("verdict", "unverified")).lower().strip()
    result["verdict"] = verdict if verdict in VERDICTS else "unverified"
    try:
        result["confidence"] = max(0, min(100, int(result.get("confidence", 0))))
    except (TypeError, ValueError):
        result["confidence"] = 0
    # keep only citation numbers that actually exist
    result["cited"] = [int(n) for n in result.get("cited", [])
                       if str(n).isdigit() and 1 <= int(n) <= len(evidence)]
    return result


def overall_verdict(claims: list) -> str:
    verdicts = [c["verdict"] for c in claims]
    for v in ("false", "misleading", "unverified"):
        if v in verdicts:
            return v
    return "true" if verdicts else "unverified"


def write_reply(claims: list, language: str) -> str:
    summary = []
    for c in claims:
        links = [c["evidence"][n - 1]["link"] for n in c["cited"][:2]]
        summary.append(f"- {c['claim']} => {c['verdict'].upper()}: {c['explanation']} "
                       f"Sources: {', '.join(links)}")
    try:
        data = chat_json(REPLY_SYSTEM.format(language=language), "\n".join(summary), 0.4)
        return data.get("reply", "")
    except Exception:
        return ""


def run_check(text: str, serp: SerpClient) -> dict:
    started = time.time()
    extracted = extract_claims(text)
    lang = extracted.get("language_code", "en")
    language = extracted.get("language_name", "English")

    def process(claim):
        evidence, trace = gather_evidence(serp, claim, lang)
        judgement = judge_claim(claim, evidence)
        return {"claim": claim["claim"], **judgement, "evidence": evidence, "trace": trace}

    with ThreadPoolExecutor(max_workers=MAX_CLAIMS) as pool:
        claims = list(pool.map(process, extracted["claims"]))

    searches = [t for c in claims for t in c["trace"]]
    return {
        "language": language,
        "overall": overall_verdict(claims),
        "claims": claims,
        "reply": write_reply(claims, language) if claims else "",
        "stats": {
            "searches": len(searches),
            "credits_used": sum(1 for t in searches if not t["cached"] and not t["error"]),
            "seconds": round(time.time() - started, 1),
        },
    }
