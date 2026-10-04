"""FwdCheck API server.  Run from the backend folder:  uvicorn app:app --reload"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from agent import run_check  # noqa: E402
from serp import SerpClient  # noqa: E402

FRONTEND  = Path(__file__).resolve().parent.parent / "frontend" / "index.html"
LANDING   = Path(__file__).resolve().parent.parent / "frontend" / "landing.html"

app = FastAPI(title="FwdCheck", version="0.1.0")
serp = SerpClient(os.getenv("SERPAPI_KEY", ""),
                  cache_path=os.getenv("CACHE_PATH", "serp_cache.sqlite"))


class CheckRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=4000)


@app.get("/")
def home():
    return FileResponse(LANDING)


@app.get("/app")
def tool():
    return FileResponse(FRONTEND)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/check")
def check(req: CheckRequest):
    try:
        return run_check(req.text.strip(), serp)
    except RuntimeError as exc:  # SerpApi problems (bad key, out of credits)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Check failed: {exc}")
