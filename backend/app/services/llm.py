"""Optional LLM client (OpenAI-compatible or Anthropic) using plain HTTP.

VYARTHX never depends on this: if no key is configured, or a call fails, every caller falls back to
deterministic logic and records `reasoning_mode = deterministic`. The LLM is only used to (a) route
free-text requests to a permitted workflow, (b) pick an item key from the knowledge base for an image,
and (c) phrase explanations. It never writes balances, weights, rules or capacities.
"""
from __future__ import annotations

import base64
import json
import logging
import re

import httpx

from app.config import settings

log = logging.getLogger("vyarthx.llm")


def enabled() -> bool:
    return settings.llm_enabled


def mode_label() -> str:
    if enabled():
        return f"LLM-assisted ({settings.LLM_PROVIDER}:{settings.LLM_MODEL or 'default'})"
    return "Deterministic agent logic (no LLM key configured)"


def _default_model() -> str:
    if settings.LLM_MODEL:
        return settings.LLM_MODEL
    return "claude-haiku-4-5" if settings.LLM_PROVIDER == "anthropic" else "gpt-4o-mini"


def chat(system: str, user: str, image_bytes: bytes | None = None, max_tokens: int = 500) -> str | None:
    if not enabled():
        return None
    try:
        if settings.LLM_PROVIDER == "anthropic":
            content: list = []
            if image_bytes:
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                            "data": base64.b64encode(image_bytes).decode()}})
            content.append({"type": "text", "text": user})
            r = httpx.post((settings.LLM_BASE_URL or "https://api.anthropic.com") + "/v1/messages",
                           headers={"x-api-key": settings.LLM_API_KEY, "anthropic-version": "2023-06-01"},
                           json={"model": _default_model(), "max_tokens": max_tokens, "system": system,
                                 "messages": [{"role": "user", "content": content}]},
                           timeout=settings.LLM_TIMEOUT)
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"])
        # OpenAI-compatible
        content = [{"type": "text", "text": user}]
        if image_bytes:
            content.append({"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()}})
        r = httpx.post((settings.LLM_BASE_URL or "https://api.openai.com/v1") + "/chat/completions",
                       headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
                       json={"model": _default_model(), "max_tokens": max_tokens,
                             "messages": [{"role": "system", "content": system},
                                          {"role": "user", "content": content if image_bytes else user}]},
                       timeout=settings.LLM_TIMEOUT)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as exc:  # network errors, bad keys, quota...
        log.warning("LLM call failed, using deterministic fallback: %s", exc)
        return None


def chat_json(system: str, user: str, image_bytes: bytes | None = None) -> dict | None:
    text = chat(system + "\nRespond with a single JSON object only.", user, image_bytes)
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
