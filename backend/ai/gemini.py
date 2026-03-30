# backend/ai/gemini.py
"""
Gemini AI Integration
─────────────────────
Wraps Google's Gemini API.  All calls are made asynchronously via
asyncio.to_thread() so they never block the event loop.

Response format
───────────────
Gemini is prompted to return a JSON object with two keys:
  {
    "reply":   "...",          // The spoken reply for TTS
    "actions": [               // Optional list of OS actions to perform
      { "type": "volume",      "value": 70 },
      { "type": "brightness",  "value": 50 },
      { "type": "open_app",    "name": "notepad" },
      { "type": "close_app",   "name": "notepad" },
      { "type": "search_web",  "query": "..." }
    ]
  }
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import textwrap
from typing import Any

log = logging.getLogger(__name__)

# System prompt sent with every request
_SYSTEM_PROMPT = textwrap.dedent("""
    You are Nova, an intelligent PC voice assistant.
    You are helpful, concise, and friendly.

    When the user asks you to perform a PC action, include it in the
    "actions" array.  Supported action types:
      - volume       (value: integer 0-100)
      - brightness   (value: integer 0-100)
      - open_app     (name: string, e.g. "notepad", "chrome", "spotify")
      - close_app    (name: string)
      - search_web   (query: string)

    ALWAYS return valid JSON matching this schema exactly:
    {
      "reply":   "<spoken response for TTS>",
      "actions": []
    }
    Do NOT include any text outside the JSON object.
""").strip()


class GeminiClient:
    """Async wrapper around the Google Generative AI SDK."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self._api_key = api_key
        self._model   = model
        self._client  = None  # lazy-init on first call

    def _get_client(self):
        if self._client is None:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(
                model_name=self._model,
                system_instruction=_SYSTEM_PROMPT,
            )
        return self._client

    # ── Public ────────────────────────────────────────────────────────────────

    async def chat(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """
        Send *user_message* to Gemini and return the parsed response dict.

        Returns a dict with keys:
          reply   (str)       – the spoken response
          actions (list[dict])– OS actions to perform
        """
        result = await asyncio.to_thread(self._blocking_chat, user_message, history or [])
        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _blocking_chat(
        self, user_message: str, history: list[dict[str, str]]
    ) -> dict[str, Any]:
        try:
            model = self._get_client()

            # Convert history format
            gemini_history = []
            for turn in history:
                gemini_history.append({"role": turn["role"], "parts": [turn["content"]]})

            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(user_message)
            raw_text = response.text.strip()

            log.debug("Gemini raw response: %s", raw_text)
            return _parse_response(raw_text)

        except Exception as exc:  # noqa: BLE001
            log.error("Gemini API error: %s", exc)
            return {"reply": "Sorry, I encountered an error. Please try again.", "actions": []}


# ── Response parser ───────────────────────────────────────────────────────────

def _parse_response(raw: str) -> dict[str, Any]:
    """
    Extract JSON from the raw Gemini output.
    Falls back gracefully if the model returns malformed JSON.
    """
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE).strip()

    try:
        data = json.loads(raw)
        reply   = str(data.get("reply", ""))
        actions = list(data.get("actions", []))
        return {"reply": reply, "actions": actions}
    except json.JSONDecodeError:
        # If we can't parse JSON, treat the whole response as the reply
        log.warning("Could not parse Gemini JSON; using raw text as reply")
        return {"reply": raw, "actions": []}
