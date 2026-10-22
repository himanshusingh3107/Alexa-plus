"""Google Knowledge answering for general Alexa+ questions with ultra-low latency."""

import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_LOCAL_INTENTS = {
    "CreateBookingIntent",
    "CheckStatusIntent",
    "SmartHomeIntent",
    "SystemHealthIntent",
    "RememberPreferenceIntent",
    "RecallMemoryIntent",
}

_LOCAL_TERMS = (
    "book",
    "booking",
    "appointment",
    "reserve",
    "reservation",
    "schedule",
    "doctor",
    "dentist",
    "table",
    "task",
    "status",
    "light",
    "lamp",
    "bulb",
    "air conditioner",
    "thermostat",
    "fan",
    "temperature",
    "health",
    "diagnostic",
    "remember",
    "preference",
    "profile",
)


def should_search_google(utterance: str, intent_name: Optional[str] = None) -> bool:
    """Return whether a request is general knowledge rather than an Alexa+ command."""
    if intent_name in _LOCAL_INTENTS:
        return False

    normalized = utterance.strip().lower()
    if not normalized or normalized.startswith("unrecognized speech handled"):
        return False

    return not any(
        re.search(rf"\b{re.escape(term)}\b", normalized)
        for term in _LOCAL_TERMS
    )


def google_search_answer(utterance: str, client: Any = None) -> Optional[str]:
    """Answer a general question using Gemini with low latency (< 1s)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set in environment.")
        return None

    try:
        from google import genai
        from google.genai import types

        if client is None:
            client = genai.Client(api_key=api_key)

        prompt = (
            "You are Alexa+, a voice assistant. Provide a clear, natural, and concise answer "
            "in 1 to 2 sentences suitable to be spoken aloud. Do NOT use markdown symbols, bullet points, or asterisks.\n\n"
            f"Question: {utterance}"
        )

        model = os.getenv("GEMINI_SEARCH_MODEL", "gemini-3.5-flash-lite")

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=100,
                temperature=0.3,
            ),
        )

        if hasattr(response, "text") and response.text:
            clean_text = response.text.replace("*", "").replace("#", "").strip()
            if clean_text:
                return clean_text

    except Exception as exc:
        logger.error(f"Error getting answer from Gemini: {exc}", exc_info=True)

    return None
