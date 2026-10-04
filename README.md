# FwdCheck: check a WhatsApp forward before you share it

FwdCheck is an AI fact-checking agent for the forwards that flood Indian family and
friends groups. Paste a message in English, Tamil, Hindi or any Indian language. FwdCheck
pulls out the factual claims, searches the live web and news with **SerpApi**, ranks the
evidence (Indian fact-checkers and official sources first), and gives each claim a
verdict with sources. It also writes a polite reply, in the forward's own language,
that you can paste back into the group.

> Built for the SerpApi India Hackathon 2026. Track: **Knowledge & Public Interest**

## Why

Misinformation in India spreads fastest through forwarded messages, often in regional
languages, and often to older relatives who won't open five fact-check sites. A fact
check is only useful if it is fast, in the right language, and easy to share back.

## How it works

```
Forward text
   │
   ▼
1. Claim extraction (LLM) ── detects language, splits into up to 3 checkable claims,
   │                         writes an English + native-language search query for each
   ▼
2. Live evidence (SerpApi), in parallel per claim
   ├─ Google Search    "<claim> fact check"     (gl=in)
   ├─ Google News      "<claim>"                (gl=in)
   └─ Google Search    native-language query    (hl=ta / hi / …)
   │
   ▼
3. Credibility ranking ── fact-checkers (Alt News, BOOM, Factly, Newschecker,
   │                      YouTurn, Vishvas News…) and official sites (.gov.in, PIB,
   │                      RBI, WHO) ranked above news outlets and other websites
   ▼
4. Verdict (LLM) ── True / False / Misleading / Unverified, using ONLY the
   │                retrieved evidence; citations are validated against it
   ▼
5. Group reply ── short, respectful correction in the forward's language
```

## How SerpApi is used (and why it matters)

SerpApi is the evidence layer. Without it, the LLM would be guessing from stale
training data, and new hoaxes appear daily.

| SerpApi engine | What FwdCheck uses it for |
| --- | --- |
| Google Search API (`engine=google`, `gl=in`) | Finds existing fact-checks and official clarifications |
| Google News API (`engine=google_news`, `gl=in`) | Finds current reporting, which matters for recent events |
| Google Search with `hl=<language>` | Finds regional-language fact-checks that English queries miss |

Every response is cached in SQLite, so repeat checks cost zero credits. The UI shows
the exact queries, result counts and credits used under "How this was searched".

## Run it locally

Requires Python 3.10+.

```bash
git clone https://github.com/<you>/fwdcheck.git
cd fwdcheck
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Fill in `.env`:

- `SERPAPI_KEY`: free key from https://serpapi.com/users/sign_up?plan=free
- `LLM_API_KEY`: a free Google Gemini key from https://aistudio.google.com/apikey
  (or use OpenAI, Groq or local Ollama; see `.env.example`)

Start the server:

```bash
cd backend
uvicorn app:app --reload
```

Open http://localhost:8000 and try one of the examples, or the ones in `samples/forwards.md`.

### API

`POST /api/check` with `{"text": "..."}` returns the language, overall verdict,
per-claim verdicts with ranked evidence and search trace, the group reply, and stats.

## Project structure

```
backend/
  app.py       FastAPI server (API + serves the frontend)
  agent.py     the pipeline: extract → search → rank → judge → reply
  serp.py      SerpApi client with SQLite cache
  sources.py   source credibility classifier
  llm.py       OpenAI-compatible LLM helper (Gemini / OpenAI / Groq / Ollama)
frontend/
  index.html   single-file UI, no build step
samples/
  forwards.md  test forwards for the demo
```

## Limitations

- A verdict is only as good as the search results. When evidence is thin, FwdCheck
  says "Unverified" instead of guessing.
- It checks text only (image forwards are on the roadmap).
- It is a helper, not an authority: always read the linked sources.

## Roadmap

- Image forwards via SerpApi's Google Lens API (find where a photo really came from)
- A WhatsApp or Telegram bot, so people can forward a message straight to FwdCheck
- A trending-hoax dashboard using Google Trends

## AI tools used

<!-- Required by hackathon rules: list the AI tools you used and how. Edit this. -->
Claude (Anthropic) helped scaffold the initial code. The app uses an LLM at runtime
for claim extraction, verdicts and replies.

## License

MIT
