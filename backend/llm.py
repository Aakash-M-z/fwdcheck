"""LLM helper using any OpenAI-compatible endpoint.

Works with Google Gemini (free tier), OpenAI, Groq, OpenRouter or a local
Ollama server. Just change LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in .env.
"""
import json
import os
import re

from openai import OpenAI

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.getenv("LLM_API_KEY", "ollama"),
            base_url=os.getenv("LLM_BASE_URL") or None,
        )
    return _client


def parse_json(text: str) -> dict:
    """Parse JSON from a model reply, tolerating ```json fences or extra prose."""
    cleaned = re.sub(r"```(?:json)?", "", text or "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Model did not return JSON: {text[:200]}")


def chat_json(system: str, user: str, temperature: float = 0.1) -> dict:
    resp = _get_client().chat.completions.create(
        model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
        temperature=temperature,
        messages=[
            {"role": "system", "content": system + "\nRespond with ONLY a JSON object."},
            {"role": "user", "content": user},
        ],
    )
    return parse_json(resp.choices[0].message.content)
