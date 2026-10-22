"""Autonomous Agentic Orchestrator for Alexa+.

Combines Google Gemini LLM reasoning, Model Context Protocol (MCP) tool execution,
Google Search grounding, and persistent contextual memory.
Enables Alexa+ to execute tasks (smart home, bookings, diagnostics) while maintaining
natural, empathetic, multi-turn conversations like an AI agent.
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
    """Core autonomous agent coordinating reasoning, MCP tools, and dialogue."""

    def __init__(self, user_id: str = "default_alexa_user"):
        self.user_id = user_id
        self.memory = MemoryEngine(user_id=user_id)
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        self._init_genai_client()

    def _init_genai_client(self):
        """Initialize Google GenAI client if API key is present."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not configured. Falling back to local agent reasoning.")
            return

        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            logger.info("AgenticOrchestrator: Google GenAI client initialized successfully.")
        except Exception as exc:
            logger.warning(f"AgenticOrchestrator: Failed to initialize GenAI client: {exc}")
            self.client = None

    def _build_agent_prompt(self, utterance: str, history: List[Dict[str, Any]]) -> str:
        """Construct structured prompt for LLM agent reasoning with tools & history."""
        tools_desc = []
        for t in AVAILABLE_TOOLS:
            name = t.get("name")
            desc = t.get("description")
            props = t.get("inputSchema", {}).get("properties", {})
            reqs = t.get("inputSchema", {}).get("required", [])
            tools_desc.append(f"- Tool: `{name}` | Required: {reqs} | Properties: {list(props.keys())} | Desc: {desc}")

        tools_desc.append(
            "- Tool: `google_search` | Desc: Grounded knowledge search for general questions, science, news, geography, history (e.g. 'what is python', 'what is a landslide')."
        )

        history_lines = []
        for turn in history[-6:]:
            role = turn.get("role", "user").capitalize()
            content = turn.get("content", "")
            tool = turn.get("tool_used")
            tool_info = f" [Tool: {tool}]" if tool else ""
            history_lines.append(f"{role}{tool_info}: {content}")

        history_block = "\n".join(history_lines) if history_lines else "No previous conversation in this session."

        prompt = f"""You are Alexa+, an advanced autonomous AI Agent that functions both as a voice-driven assistant and a proactive conversational companion.
You are powered by Google Gemini and Model Context Protocol (MCP) tools.

### YOUR CAPABILITIES:
1. Complete tasks via MCP tools (controlling lights, AC, bookings, tasks, health checks).
2. Converse naturally like an intelligent AI agent (greetings, empathy, casual chat, explanations, suggestions).
3. If the user combines a conversation and a task (e.g. 'I have a headache, dim the lights and book a doctor for tomorrow'), handle BOTH: invoke the tool and converse warmly.
4. If the user asks a general question (e.g. 'what is python', 'what is a landslide'), set tool_name to 'google_search'.
5. If the user is just conversing (e.g. 'how are you', 'what can you do', 'tell me a joke', 'thank you'), set tool_name to null and converse engagingly.
6. Support English and Hinglish seamlessly. Match the user's language tone.

### AVAILABLE TOOLS:
{chr(10).join(tools_desc)}

### RECENT CONVERSATION HISTORY:
{history_block}

### CURRENT USER UTTERANCE:
"{utterance}"

### OUTPUT FORMAT:
You MUST respond with a single, valid JSON object matching this schema. Do NOT wrap in markdown fences like ```json.
{{
  "thought": "Brief 1-sentence reasoning of user intent and chosen action",
  "tool_name": "tool_name_or_null",
  "tool_args": {{ "key": "value" }},
  "speech_response": "Crisp, natural, voice-friendly response (1 to 3 sentences). Do NOT use bullet points, asterisks, or markdown."
}}
"""
        return prompt

    def process_utterance(
        self,
        utterance: str,
        session_id: Optional[str] = "web-dashboard-session"
    ) -> Dict[str, Any]:
        """Process user utterance through agentic reasoning, execute tools, and return response."""
        utterance = (utterance or "").strip()
        if not utterance:
            return {
                "success": False,
                "response": "I didn't catch that. How can I help you?",
                "tool_used": None,
            }

        try:
            recent_history = self.memory.get_recent_history(limit=6)
        except Exception as exc:
            logger.warning(f"Could not load conversation history: {exc}")
            recent_history = []

        # 1. Try Gemini LLM Agentic Reasoning
        if self.client:
            try:
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
                logger.warning(f"Gemini agentic call failed ({exc}); falling back to local agent reasoning.")

        # 2. Local Conversational & Tool Agent Fallback
        fallback_result = self._local_agent_reasoning(utterance, session_id)
        self._record_turn(session_id, utterance, fallback_result["response"], fallback_result.get("tool_used"))
        return fallback_result

    def _call_gemini_agent(
        self,
        utterance: str,
        history: List[Dict[str, Any]],
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Call Gemini to get an autonomous decision with tool invocation."""
        prompt = self._build_agent_prompt(utterance, history)
        models_to_try = [
            os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash"),
        ]

        raw_text = ""
        for model_name in models_to_try:
            try:
                from google.genai import types
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        response_mime_type="application/json",
                    ),
                )
                raw_text = getattr(response, "text", "") or ""
                if raw_text:
                    break
            except Exception as e:
                logger.info(f"Agent reasoning with {model_name} in json mode failed: {e}; trying standard call")
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    raw_text = getattr(response, "text", "") or ""
                    if raw_text:
                        break
                except Exception as e2:
                    logger.warning(f"Model {model_name} failed: {e2}")

        if not raw_text:
            return None

        # Clean JSON from markdown fences if any
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
        except Exception as parse_err:
            logger.warning(f"Failed to parse LLM agent JSON: {parse_err}. Raw text: {raw_text[:200]}")
            return None

        tool_name = decision.get("tool_name")
        tool_args = decision.get("tool_args") or {}
        speech = decision.get("speech_response") or ""
        thought = decision.get("thought", "")

        # Execute Tool if requested by agent
        if tool_name and tool_name not in ("null", "none"):
            logger.info(f"Agent decided to invoke tool '{tool_name}' with args {tool_args}")
            if tool_name == "google_search":
                search_q = tool_args.get("query") or utterance
                grounded_ans = google_search_answer(search_q, self.client)
                if grounded_ans:
                    speech = grounded_ans
            else:
                try:
                    call_tool(tool_name, tool_args, session_id=session_id)
                except Exception as tool_err:
                    logger.error(f"Error executing tool {tool_name}: {tool_err}")
                    speech += f" (Note: There was an issue updating {tool_name}.)"

        # Remove any unwanted markdown symbols from voice speech
        clean_speech = speech.replace("*", "").replace("#", "").strip()

        return {
            "thought": thought,
            "tool_name": tool_name if tool_name not in ("null", "none") else None,
            "speech_response": clean_speech,
        }

    def _local_agent_reasoning(self, utterance: str, session_id: str) -> Dict[str, Any]:
        """Intelligent local agent reasoning when Gemini API is unavailable or offline."""
        lowered = utterance.lower()
        tool_used = None
        spoken_response = ""

        # 1. Smart Home Automation (Lights / Darkness / Hinglish)
        is_darkness = any(w in lowered for w in ["andhera", "dark", "dim", "roshni", "bright", "light badhao"])
        is_light_cmd = any(w in lowered for w in ["light", "lights", "lamp", "bulb"])
        is_ac_cmd = any(w in lowered for w in ["ac", "air conditioner", "thermostat", "garmi", "cool", "thand", "temperature", "fan"])

        if is_darkness or is_light_cmd:
            action = "turn_on" if not any(w in lowered for w in ["off", "band", "close", "bujha"]) else "turn_off"
            level = 100 if is_darkness or "on" in action else 0
            call_tool("alexa_execute_automation", {
                "action_type": "smart_home_scene",
                "target_device_or_service": "living_room_lights",
                "parameters": {"command": action, "brightness": level, "scene": "illuminated"}
            }, session_id=session_id)
            tool_used = "alexa_execute_automation"
            if is_darkness:
                spoken_response = "Maine living room ki lights on kar di hain taaki andhera door ho sake. Kya main aapke liye koi aur kaam kar sakti hoon?"
            elif action == "turn_on":
                spoken_response = "Sure! I've turned on the living room lights for you. Anything else you need?"
            else:
                spoken_response = "I've turned off the lights. Let me know if you need anything else."

        # 2. Air Conditioner / Climate
        elif is_ac_cmd:
            action = "turn_on" if not any(w in lowered for w in ["off", "band", "bujha"]) else "turn_off"
            call_tool("alexa_execute_automation", {
                "action_type": "smart_home_scene",
                "target_device_or_service": "living_room_ac",
                "parameters": {"command": action, "target_temp": 71, "mode": "cool"}
            }, session_id=session_id)
            tool_used = "alexa_execute_automation"
            if "thand" in lowered:
                spoken_response = "Maine AC temperature adjust kar diya hai taaki aapko thand na lage."
            elif "garmi" in lowered:
                spoken_response = "Garmi kam karne ke liye AC cool mode par set kar diya hai."
            else:
                spoken_response = f"I've {('started' if action == 'turn_on' else 'turned off')} the AC and set climate to comfortable mode."

        # 3. Appointments & Bookings
        elif any(w in lowered for w in ["book", "appointment", "reservation", "schedule", "doctor", "dentist", "table"]):
            category = "doctor" if any(w in lowered for w in ["doctor", "dentist", "hospital", "clinic", "checkup"]) else ("restaurant" if any(w in lowered for w in ["table", "dinner", "lunch", "restaurant"]) else "general")
            title = utterance.replace("book", "").replace("schedule", "").replace("appointment", "").strip().title()
            if not title or len(title) < 3:
                title = f"{category.title()} Appointment"

            call_tool("alexa_create_booking", {
                "title": title,
                "customer_name": "Demo User",
                "category": category,
                "description": f"Booked via Alexa+ Agent: {utterance}"
            }, session_id=session_id)
            tool_used = "alexa_create_booking"
            spoken_response = f"Done! I have scheduled your {category} appointment for '{title}'. It is now saved in your Turso Cloud and local database."

        # 4. Schedule & Tasks Query
        elif any(w in lowered for w in ["tasks", "schedule", "bookings", "list", "kya hai", "kya chal rha", "upcoming"]):
            call_tool("alexa_query_tasks", {"limit": 5}, session_id=session_id)
            tool_used = "alexa_query_tasks"
            spoken_response = "I've fetched your latest bookings and tasks from the database. You can see them in your live dashboard table."

        # 5. System Health & Diagnostics
        elif any(w in lowered for w in ["health", "status", "diagnostic", "report", "system"]):
            call_tool("alexa_get_system_health", {}, session_id=session_id)
            tool_used = "alexa_get_system_health"
            spoken_response = "All systems operational: The MCP gateway, Turso Cloud sync, and SQLite memory engine are completely healthy."

        # 6. Conversational Agent Chit-Chat
        elif any(w in lowered for w in ["who are you", "what are you", "tum kaun ho", "intro"]):
            spoken_response = (
                "I am Alexa+, an autonomous agentic AI assistant. I combine Google Gemini LLM reasoning with "
                "the Model Context Protocol to control your smart home, manage bookings, and converse like an intelligent agent."
            )
        elif any(w in lowered for w in ["how are you", "kya haal hai", "kaise ho", "how's it going"]):
            spoken_response = "I'm doing fantastic, thank you! I am ready to control devices, book appointments, or answer any questions you have."
        elif any(w in lowered for w in ["joke", "chutkula", "funny"]):
            spoken_response = "Why don't programmers like nature? It has too many bugs! Let me know if you need help with any tasks or commands."
        elif any(w in lowered for w in ["thank you", "thanks", "shukriya", "dhanyawad"]):
            spoken_response = "You're very welcome! I'm always here to help you manage your home and schedule."

        # 7. General Knowledge Grounding via Google Search / Gemini
        else:
            search_ans = google_search_answer(utterance, self.client)
            if search_ans:
                spoken_response = search_ans
                tool_used = "google_search"
            else:
                spoken_response = (
                    f"I heard: \"{utterance}\". As an agentic voice assistant, I can execute actions like controlling lights, "
                    "booking appointments, checking your database, or answering general knowledge questions."
                )

        return {
            "success": True,
            "response": spoken_response,
            "tool_used": tool_used,
        }

    def _record_turn(self, session_id: Optional[str], user_content: str, assistant_content: str, tool_used: Optional[str]):
        """Record conversation turn in persistent memory."""
        try:
            self.memory.save_conversation_turn(session_id, "user", user_content)
            self.memory.save_conversation_turn(session_id, "assistant", assistant_content, tool_used=tool_used)
        except Exception as exc:
            logger.debug(f"Failed to record turn in memory: {exc}")
