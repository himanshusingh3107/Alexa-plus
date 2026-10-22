"""Google Search and Knowledge grounding for general Alexa+ questions."""

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
    """Answer a general question using Gemini grounded with Google knowledge."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY is not set in environment.")
        return None

    try:
        from google import genai
        if client is None:
            client = genai.Client(api_key=api_key)

        prompt = (
            "You are Alexa+, a smart voice assistant. Answer the user's question clearly, "
            "concisely, and accurately in 2 to 3 sentences suitable to be spoken aloud. "
            "Do NOT use markdown symbols, bullet points, or asterisks.\n\n"
            f"Question: {utterance}"
        )

        models_to_try = [
            os.getenv("GEMINI_SEARCH_MODEL", "gemini-3.5-flash-lite"),
            os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash"),
        ]

        # 1. Try search grounding first, fall back cleanly if quota exceeded
        for model in models_to_try:
            try:
                from google.genai import types
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    ),
                )
                if hasattr(response, "text") and response.text:
                    clean_text = response.text.replace("*", "").replace("#", "").strip()
                    if clean_text:
                        return clean_text
            except Exception as search_err:
                logger.info(f"Search grounding with {model} unavailable ({search_err}); falling back to standard generation.")

            # 2. Standard direct generation (super fast, no 429 quota exhaustion)
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                if hasattr(response, "text") and response.text:
                    clean_text = response.text.replace("*", "").replace("#", "").strip()
                    if clean_text:
                        return clean_text
            except Exception as gen_err:
                logger.warning(f"Standard generation with {model} failed: {gen_err}")

    except Exception as exc:
        logger.error(f"Error getting answer from Gemini: {exc}", exc_info=True)

    return None
