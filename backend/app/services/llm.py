"""Optional LLM client (Anthropic or Google Gemini) using plain HTTP.

VYARTHX never depends on this: if no key is configured, or a call fails, every caller falls back to
deterministic logic. The LLM is only used to phrase explanations and (optionally) describe a photo.
It never writes balances, weights, rules or capacities.

Provider is picked automatically: ANTHROPIC_API_KEY wins if set, otherwise GEMINI_API_KEY.
"""
from __future__ import annotations

import httpx

from app.config import settings

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


def complete(prompt: str, system: str = "", image_jpeg_b64: str | None = None, max_tokens: int = 220) -> str:
    """Return the model's text reply. Raises on any error (callers catch and fall back)."""
    if settings.LLM_PROVIDER == "anthropic":
        content: list = []
        if image_jpeg_b64:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_jpeg_b64}})
        content.append({"type": "text", "text": prompt})
        body = {"model": settings.LLM_MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}
        if system:
            body["system"] = system
        r = httpx.post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                       json=body, timeout=25)
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()

    if settings.LLM_PROVIDER == "gemini":
        user_content: str | list = prompt
        if image_jpeg_b64:
            user_content = [{"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image_jpeg_b64}}]
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user_content}]
        # Gemini "thinking" tokens count against max_tokens, so leave generous headroom.
        r = httpx.post(GEMINI_URL, headers={"Authorization": f"Bearer {settings.GEMINI_API_KEY}"},
                       json={"model": settings.GEMINI_MODEL, "max_tokens": max_tokens + 512, "messages": messages}, timeout=15)
        r.raise_for_status()
        return (r.json()["choices"][0]["message"]["content"] or "").strip()

    raise RuntimeError("No LLM key configured")
