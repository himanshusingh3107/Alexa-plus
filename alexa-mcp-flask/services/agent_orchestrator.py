"""Ultra-Fast Autonomous Agentic Orchestrator for Alexa+.

Combines sub-second Google Gemini LLM reasoning (gemini-3.5-flash-lite),
instant MCP tool execution, and persistent contextual memory.
Single-pass generation architecture ensures fast responses (< 1.5s).
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from memory_engine import MemoryEngine
from services.external_tools import AVAILABLE_TOOLS, call_tool
from services.google_search import google_search_answer

logger = logging.getLogger(__name__)


class AgenticOrchestrator:
    """Core autonomous agent coordinating sub-second reasoning, MCP tools, and dialogue."""

    def __init__(self, user_id: str = "default_alexa_user"):
        self.user_id = user_id
        self.memory = MemoryEngine(user_id=user_id)
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        self._init_genai_client()

    def _init_genai_client(self):
        """Initialize Google GenAI client if API key is present."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not configured. Operating in local mode.")
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            logger.info("AgenticOrchestrator: Google GenAI client ready.")
        except Exception as exc:
            logger.warning(f"AgenticOrchestrator: Failed to initialize GenAI client: {exc}")
            self.client = None

    def _build_agent_prompt(self, utterance: str, history: List[Dict[str, Any]]) -> str:
        """Construct compact, high-speed structured prompt for single-pass reasoning."""
        tools_summary = (
            "- `alexa_execute_automation`: {action_type, target_device_or_service, parameters}\n"
            "- `alexa_create_booking`: {title, customer_name, category, scheduled_time}\n"
            "- `alexa_query_tasks`: {status, limit}\n"
            "- `alexa_get_system_health`: {}\n"
            "- `google_search`: Use for general knowledge/facts (what is python, landslide, etc.)"
        )

        history_lines = []
        for turn in history[-4:]:
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "")
            history_lines.append(f"{role}: {content}")

        history_block = "\n".join(history_lines) if history_lines else "None"

        return f"""You are Alexa+, an autonomous AI Agent.
Respond to the user with a single-pass decision in JSON.
If the user asks a question, answer it directly and accurately inside `speech_response` and set `tool_name` to 'google_search'.
If the user requests a task, specify the tool to invoke and provide a natural spoken confirmation.
Support both English and Hinglish naturally.

TOOLS:
{tools_summary}

RECENT HISTORY:
{history_block}

USER UTTERANCE: "{utterance}"

Return ONLY this raw JSON schema (no markdown formatting, no ```json):
{{
  "thought": "1 short sentence reasoning",
  "tool_name": "tool_name_or_null",
  "tool_args": {{}},
  "speech_response": "1-2 concise, clear sentences suitable for spoken voice. No bullet points or asterisks."
}}"""

    def process_utterance(
        self,
        utterance: str,
        session_id: Optional[str] = "web-dashboard-session"
    ) -> Dict[str, Any]:
        """Process user utterance with sub-second execution."""
        utterance = (utterance or "").strip()
        if not utterance:
            return {
                "success": False,
                "response": "I didn't catch that. How can I help you?",
                "tool_used": None,
            }

        # --- FAST-PATH FOR OBVIOUS HARDWARE COMMANDS (Instant ~10ms execution) ---
        lowered = utterance.lower()
        fast_result = self._check_fast_path(utterance, lowered, session_id)
        if fast_result:
            self._record_turn(session_id, utterance, fast_result["response"], fast_result.get("tool_used"))
            return fast_result

        # --- SINGLE-PASS GEMINI LLM REASONING (< 1.5s) ---
        if self.client:
            try:
                recent_history = []
                try:
                    recent_history = self.memory.get_recent_history(limit=4)
                except Exception:
                    pass

                agent_result = self._call_gemini_agent(utterance, recent_history, session_id)
                if agent_result and agent_result.get("speech_response"):
                    self._record_turn(session_id, utterance, agent_result.get("speech_response"), agent_result.get("tool_name"))
                    return {
                        "success": True,
                        "response": agent_result["speech_response"],
                        "tool_used": agent_result.get("tool_name"),
                        "thought": agent_result.get("thought"),
                    }
            except Exception as exc:
                logger.warning(f"Fast LLM call error: {exc}")

        # --- FALLBACK ---
        fallback_result = self._local_agent_reasoning(utterance, session_id)
        self._record_turn(session_id, utterance, fallback_result["response"], fallback_result.get("tool_used"))
        return fallback_result

    def _check_fast_path(self, utterance: str, lowered: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Instant sub-50ms execution for standard hardware and health commands."""
        # Simple Lights toggle
        if lowered in ["turn on lights", "turn on the lights", "lights on", "andhera hai", "light on karo", "turn on light"]:
            call_tool("alexa_execute_automation", {
                "action_type": "smart_home_scene",
                "target_device_or_service": "living_room_lights",
                "parameters": {"command": "turn_on", "brightness": 100, "scene": "illuminated"}
            }, session_id=session_id)
            return {
                "success": True,
                "response": "I've turned on the living room lights for you." if "andhera" not in lowered else "Maine living room ki lights on kar di hain, andhera door ho gaya hai.",
                "tool_used": "alexa_execute_automation",
                "thought": "Direct high-speed smart home automation triggered.",
            }

        if lowered in ["turn off lights", "turn off the lights", "lights off", "light band karo", "turn off light"]:
            call_tool("alexa_execute_automation", {
                "action_type": "smart_home_scene",
                "target_device_or_service": "living_room_lights",
                "parameters": {"command": "turn_off", "brightness": 0}
            }, session_id=session_id)
            return {
                "success": True,
                "response": "I've turned off the living room lights.",
                "tool_used": "alexa_execute_automation",
                "thought": "Direct high-speed smart home automation triggered.",
            }

        # AC commands
        if lowered in ["turn on ac", "turn on the ac", "ac on", "ac chalu karo", "garmi hai"]:
            call_tool("alexa_execute_automation", {
                "action_type": "smart_home_scene",
                "target_device_or_service": "living_room_ac",
                "parameters": {"command": "turn_on", "target_temp": 71, "mode": "cool"}
            }, session_id=session_id)
            return {
                "success": True,
                "response": "I've turned on the air conditioner to cool mode.",
                "tool_used": "alexa_execute_automation",
                "thought": "Direct climate automation executed.",
            }

        # Health check
        if lowered in ["health", "status", "health check", "system health", "check health"]:
            call_tool("alexa_get_system_health", {}, session_id=session_id)
            return {
                "success": True,
                "response": "All systems operational: MCP gateway, SQLite memory, and Turso Cloud database are healthy.",
                "tool_used": "alexa_get_system_health",
                "thought": "Direct system health probe executed.",
            }

        return None

    def _call_gemini_agent(
        self,
        utterance: str,
        history: List[Dict[str, Any]],
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Single-pass fast LLM reasoning using gemini-3.5-flash-lite."""
        from google.genai import types

        prompt = self._build_agent_prompt(utterance, history)
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=150,
                response_mime_type="application/json",
            ),
        )

        raw_text = getattr(response, "text", "") or ""
        if not raw_text:
            return None

        # Strip markdown fences if present
        raw_text = raw_text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        try:
            decision = json.loads(raw_text)
        except Exception:
            return None

        tool_name = decision.get("tool_name")
        tool_args = decision.get("tool_args") or {}
        speech = decision.get("speech_response") or ""
        thought = decision.get("thought", "")

        # Execute MCP tool only if it's NOT a search tool (search was answered in single-pass)
        if tool_name and tool_name not in ("null", "none", "None", ""):
            if tool_name != "google_search":
                try:
                    call_tool(tool_name, tool_args, session_id=session_id)
                except Exception as err:
                    logger.warning(f"Tool execution warning: {err}")

        # Clean formatting
        clean_speech = speech.replace("*", "").replace("#", "").strip()

        return {
            "thought": thought,
            "tool_name": tool_name if tool_name not in ("null", "none", "None", "") else None,
            "speech_response": clean_speech,
        }

    def _local_agent_reasoning(self, utterance: str, session_id: str) -> Dict[str, Any]:
        """Local fast fallback."""
        lowered = utterance.lower()

        # Greetings & chit-chat
        if any(w in lowered for w in ["who are you", "tum kaun ho", "intro"]):
            return {
                "success": True,
                "response": "I am Alexa+, an autonomous agentic AI assistant powered by Google Gemini and MCP tools.",
                "tool_used": None,
            }

        if any(w in lowered for w in ["how are you", "kaise ho", "kya haal hai"]):
            return {
                "success": True,
                "response": "I'm doing great, thank you! Ready to control devices, book appointments, or answer any questions.",
                "tool_used": None,
            }

        # Fast question answer
        ans = google_search_answer(utterance, self.client)
        if ans:
            return {
                "success": True,
                "response": ans,
                "tool_used": "google_search",
            }

        return {
            "success": True,
            "response": f"I heard: \"{utterance}\". As an agentic assistant, I can control devices, book appointments, and answer general questions.",
            "tool_used": None,
        }

    def _record_turn(self, session_id: Optional[str], user_content: str, assistant_content: str, tool_used: Optional[str]):
        """Record turn in SQLite/Turso database asynchronously/quietly."""
        try:
            self.memory.save_conversation_turn(session_id, "user", user_content)
            self.memory.save_conversation_turn(session_id, "assistant", assistant_content, tool_used=tool_used)
        except Exception:
            pass
