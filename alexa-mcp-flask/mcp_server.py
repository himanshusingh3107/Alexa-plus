"""Standalone Model Context Protocol (MCP) Server using stdio transport.

Provides direct LLM integration via stdio/subprocess for the Alexa+ platform.
Exposes database task/booking tools, contextual memory persistence,
system health diagnostics, live resources, and assistant prompt templates.
"""

import sys
import os
import pprint
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from config.database import (
    init_db, create_task_booking, update_task_booking,
    query_task_bookings, record_live_event, get_system_counts, query_latest_events,
)
from services.external_tools import (
    AVAILABLE_TOOLS, AVAILABLE_RESOURCES,
    call_tool as ext_call_tool, read_resource as ext_read_resource,
)

# Contextual Memory Engine integration (with graceful fallback)
try:
    import memory_engine
except ImportError:
    try:
        from services import memory_engine
    except ImportError:
        memory_engine = None

# Configure logging strictly to sys.stderr to avoid stdout corruption in stdio transport
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] [alexa-plus-mcp] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("alexa_plus_mcp")

# MCP Server Instance
server = Server("alexa-plus-mcp")

# In-memory preference store for user state caching
_in_memory_preferences: Dict[str, Dict[str, Any]] = {
    "default_user": {
        "favorite_restaurant": "Olive Garden", "preferred_doctor": "Dr. Smith",
        "preferred_thermostat_temp": "71F", "preferred_commute_mode": "cab",
    }
}


# ------------------------------------------------------------------------------
# Memory & Context Tool Implementations
# ------------------------------------------------------------------------------

def _call_memory_engine(fn_names: tuple, *args, **kwargs) -> Optional[Any]:
    """Helper to dispatch calls to memory_engine functions or class methods."""
    if memory_engine is None:
        return None
    for name in fn_names:
        fn = getattr(memory_engine, name, None)
        if callable(fn):
            try:
                return fn(*args, **kwargs)
            except Exception as err:
                logger.warning(f"Error calling {name} in memory_engine: {err}")
    cls = getattr(memory_engine, "MemoryEngine", None)
    if cls and callable(cls):
        try:
            inst = cls()
            for name in fn_names:
                method = getattr(inst, name, None)
                if callable(method):
                    return method(*args, **kwargs)
        except Exception as err:
            logger.warning(f"Error calling MemoryEngine.{name}: {err}")
    return None


def execute_memory_fetch(user_id: str) -> Dict[str, Any]:
    """Retrieve user profile, preferences, and recent history from memory engine."""
    logger.info(f"Executing memory_fetch for user: '{user_id}'")
    engine_res = _call_memory_engine(("memory_fetch", "get_user_profile", "get_user_memory", "fetch_memory", "get_memory"), user_id)
    if engine_res is not None:
        return engine_res

    user_tasks = query_task_bookings(limit=5)
    recent_events = query_latest_events(limit=5)
    user_prefs = _in_memory_preferences.get(user_id, {
        "favorite_restaurant": "Olive Garden", "preferred_doctor": "Dr. Smith", "preferred_thermostat_temp": "71F",
    })
    return {
        "success": True, "user_id": user_id,
        "profile": {"name": user_id.replace("_", " ").title(), "status": "active", "tier": "plus"},
        "preferences": user_prefs, "recent_tasks": user_tasks,
        "recent_event_types": [e["event_type"] for e in recent_events],
        "source": "memory_engine" if memory_engine is not None else "database_fallback",
    }


def execute_memory_save_preference(user_id: str, key: str, value: str, category: str = "general") -> Dict[str, Any]:
    """Persist user preference to memory engine and record database telemetry."""
    logger.info(f"Executing memory_save_preference: '{key}'='{value}' ({category}) for '{user_id}'")
    saved_in_engine = _call_memory_engine(("memory_save_preference", "save_user_preference", "save_preference", "set_preference"), user_id, key, value, category) is not None

    if user_id not in _in_memory_preferences:
        _in_memory_preferences[user_id] = {}
    _in_memory_preferences[user_id][key] = value

    record_live_event(
        event_type="MEMORY_PREFERENCE_SAVED",
        details={"user_id": user_id, "key": key, "value": value, "category": category, "saved_in_engine": saved_in_engine},
        session_id="stdio-session",
    )
    return {
        "success": True, "message": f"Successfully stored preference '{key}' = '{value}' for user '{user_id}'.",
        "user_id": user_id, "key": key, "value": value, "category": category, "saved_in_engine": saved_in_engine,
    }


def execute_proactive_notify(user_id: str, message: str, priority: str = "normal") -> Dict[str, Any]:
    """Simulate a proactive notification event and log to SQL database."""
    logger.info(f"Executing proactive_notify for user '{user_id}' [{priority}]: {message}")
    notified_via_engine = _call_memory_engine(("proactive_notify", "send_notification", "queue_notification", "notify"), user_id, message, priority) is not None

    event = record_live_event(
        event_type="PROACTIVE_NOTIFICATION_QUEUED",
        details={"user_id": user_id, "message": message, "priority": priority, "notified_via_engine": notified_via_engine, "timestamp": datetime.now(timezone.utc).isoformat()},
        session_id="stdio-session",
    )
    return {
        "success": True, "message": f"Proactive notification queued for delivery to user '{user_id}'.",
        "user_id": user_id, "notification_text": message, "priority": priority, "status": "queued", "event_id": event["id"],
    }


def execute_context_summary(user_id: str) -> Dict[str, Any]:
    """Compile comprehensive context summary for LLM prompt augmentation."""
    logger.info(f"Executing context_summary for user: '{user_id}'")
    engine_res = _call_memory_engine(("context_summary", "get_context_summary", "generate_context_summary"), user_id)
    if engine_res is not None:
        return engine_res

    active_tasks = query_task_bookings(status="pending", limit=5)
    confirmed_tasks = query_task_bookings(status="confirmed", limit=5)
    counts = get_system_counts()
    user_prefs = _in_memory_preferences.get(user_id, {})
    summary_text = (
        f"User ID: {user_id}\nActive Pending Tasks: {len(active_tasks)}, Confirmed Bookings: {len(confirmed_tasks)}\n"
        f"Preferences: {', '.join(f'{k}: {v}' for k, v in user_prefs.items()) if user_prefs else 'None recorded'}\n"
        f"Total Database Tasks: {counts.get('total_tasks', 0)}"
    )
    return {
        "success": True, "user_id": user_id, "summary": summary_text, "preferences": user_prefs,
        "pending_tasks_count": len(active_tasks), "confirmed_tasks_count": len(confirmed_tasks), "system_metrics": counts,
    }


# ------------------------------------------------------------------------------
# Additional Memory Tools Definitions (MCP Tool Objects)
# ------------------------------------------------------------------------------

ADDITIONAL_MEMORY_TOOLS: List[types.Tool] = [
    types.Tool(
        name="memory_fetch",
        description="Retrieve user profile, preferences, and recent conversation history from the contextual memory engine.",
        inputSchema={"type": "object", "properties": {"user_id": {"type": "string", "description": "Unique identifier for the user"}}, "required": ["user_id"]},
    ),
    types.Tool(
        name="memory_save_preference",
        description="Persist a user preference (e.g. favorite restaurant, preferred temperature) into the memory engine.",
        inputSchema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Unique identifier for the user"},
                "key": {"type": "string", "description": "Preference key name"},
                "value": {"type": "string", "description": "Preference value to store"},
                "category": {"type": "string", "description": "Preference category", "default": "general"},
            },
            "required": ["user_id", "key", "value"],
        },
    ),
    types.Tool(
        name="proactive_notify",
        description="Simulate or queue a proactive voice notification or alert for an Alexa user.",
        inputSchema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "Target user ID"},
                "message": {"type": "string", "description": "Notification message to deliver"},
                "priority": {"type": "string", "enum": ["low", "normal", "high", "urgent"], "default": "normal"},
            },
            "required": ["user_id", "message"],
        },
    ),
    types.Tool(
        name="context_summary",
        description="Return full context summary (user state, bookings, preferences, and system counts) for LLM prompting.",
        inputSchema={"type": "object", "properties": {"user_id": {"type": "string", "description": "Unique identifier for the user"}}, "required": ["user_id"]},
    ),
]


# ------------------------------------------------------------------------------
# Tool Registration & Execution Handlers
# ------------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Register and list all available MCP tools."""
    logger.info("Listing registered MCP tools")
    tools: list[types.Tool] = [
        types.Tool(name=t["name"], description=t.get("description", ""), inputSchema=t.get("inputSchema", {}))
        for t in AVAILABLE_TOOLS
    ]
    tools.extend(ADDITIONAL_MEMORY_TOOLS)
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> list[types.TextContent]:
    """Execute requested MCP tool and return formatted TextContent."""
    args = arguments or {}
    logger.info(f"Call tool requested: '{name}' with args {args}")

    try:
        if name == "memory_fetch":
            result = execute_memory_fetch(str(args.get("user_id", "default_user")).strip())
        elif name == "memory_save_preference":
            k, v = str(args.get("key", "")).strip(), str(args.get("value", "")).strip()
            if not k or not v:
                raise ValueError("Both 'key' and 'value' are required for memory_save_preference.")
            result = execute_memory_save_preference(str(args.get("user_id", "default_user")).strip(), k, v, str(args.get("category", "general")).strip())
        elif name == "proactive_notify":
            msg = str(args.get("message", "")).strip()
            if not msg:
                raise ValueError("Field 'message' is required for proactive_notify.")
            result = execute_proactive_notify(str(args.get("user_id", "default_user")).strip(), msg, str(args.get("priority", "normal")).strip().lower())
        elif name == "context_summary":
            result = execute_context_summary(str(args.get("user_id", "default_user")).strip())
        else:
            raw_res = ext_call_tool(name, args, session_id="stdio-session")
            contents = raw_res.get("content", [])
            text_out = contents[0].get("text", pprint.pformat(raw_res, sort_dicts=False)) if isinstance(contents, list) and contents else pprint.pformat(raw_res, sort_dicts=False)
            return [types.TextContent(type="text", text=text_out)]

        return [types.TextContent(type="text", text=pprint.pformat(result, sort_dicts=False))]

    except Exception as exc:
        logger.error(f"Error executing tool '{name}': {exc}", exc_info=True)
        return [types.TextContent(type="text", text=pprint.pformat({"success": False, "error": str(exc), "tool": name}, sort_dicts=False))]


# ------------------------------------------------------------------------------
# Resource Registration & Reading Handlers
# ------------------------------------------------------------------------------

@server.list_resources()
async def list_resources() -> list[types.Resource]:
    """Register and list available MCP resources."""
    logger.info("Listing registered MCP resources")
    return [
        types.Resource(
            uri=types.AnyUrl(res["uri"]),
            name=res["name"],
            description=res.get("description"),
            mimeType=res.get("mimeType", "text/plain"),
        )
        for res in AVAILABLE_RESOURCES
    ]


@server.read_resource()
async def read_resource(uri: types.AnyUrl) -> str:
    """Read resource URI content using the existing resource dispatcher."""
    uri_str = str(uri)
    logger.info(f"Reading MCP resource: {uri_str}")
    raw_res = ext_read_resource(uri_str)
    if isinstance(raw_res, dict) and raw_res.get("contents"):
        return raw_res["contents"][0].get("text", "")
    return pprint.pformat(raw_res, sort_dicts=False)


# ------------------------------------------------------------------------------
# Prompt Templates Registration & Retrieval
# ------------------------------------------------------------------------------

@server.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    """Register and list available assistant prompt templates."""
    logger.info("Listing registered MCP prompt templates")
    return [
        types.Prompt(
            name="alexa-assistant",
            description="System prompt template defining the Alexa+ conversational AI assistant persona and capabilities.",
            arguments=[
                types.PromptArgument(name="user_name", description="Name of the user interacting with Alexa+", required=False),
                types.PromptArgument(name="context_summary", description="Summary of current context and preferences", required=False),
            ],
        ),
        types.Prompt(
            name="booking-helper",
            description="Specialized prompt template guiding multi-turn booking and reservation dialogues.",
            arguments=[
                types.PromptArgument(name="category", description="Category of the booking (e.g. doctor, restaurant)", required=False),
                types.PromptArgument(name="user_name", description="Name of the user or customer requesting the booking", required=False),
            ],
        ),
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: Optional[Dict[str, str]] = None) -> types.GetPromptResult:
    """Generate prompt content based on template name and arguments."""
    args = arguments or {}
    logger.info(f"Fetching prompt template: '{name}' with args {args}")

    if name == "alexa-assistant":
        user_name = args.get("user_name", "valued user")
        context_summary = args.get("context_summary", "No prior context available.")
        prompt_text = (
            f"You are Alexa+, an advanced context-aware AI voice assistant.\n"
            f"Interacting with: {user_name}\n\n"
            f"Context & Memory:\n{context_summary}\n\n"
            f"Guidelines:\n"
            f"1. Voice-Optimized: Keep responses concise, warm, and natural (under 3 sentences when possible).\n"
            f"2. Context-Aware: Proactively reference preferences and confirmed tasks.\n"
            f"3. Action-Oriented: Use MCP tools directly for bookings, tasks, automations, and memory updates.\n"
            f"4. Confirmations: Confirm key parameters before finalizing bookings."
        )
        return types.GetPromptResult(
            description="Alexa+ Assistant System Prompt",
            messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text=prompt_text))],
        )

    elif name == "booking-helper":
        category = args.get("category", "general")
        user_name = args.get("user_name", "Customer")
        prompt_text = (
            f"You are the Alexa+ Booking Specialist for '{category}' services.\n"
            f"Assisting: {user_name}\n\n"
            f"Workflow:\n"
            f"1. Inquire for missing details: title/service, date/time, and category specifics.\n"
            f"2. Execute `alexa_create_booking` when required information is verified.\n"
            f"3. Present booking confirmation and offer follow-up reminders or smart scenes."
        )
        return types.GetPromptResult(
            description="Alexa+ Booking Helper Prompt",
            messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text=prompt_text))],
        )

    else:
        raise ValueError(f"Unknown prompt template requested: '{name}'")


# ------------------------------------------------------------------------------
# Main Entry Point (stdio transport execution)
# ------------------------------------------------------------------------------

async def main() -> None:
    """Initialize database and run MCP stdio server."""
    logger.info("Initializing Alexa+ MCP Stdio Server...")
    try:
        init_db()
        logger.info("SQL database tables initialized successfully.")
    except Exception as exc:
        logger.error(f"Database initialization error (continuing): {exc}", exc_info=True)

    logger.info("Starting stdio transport communication loop...")
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
