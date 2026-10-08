"""Specialized task and tool execution logic written in pure Python.

Uses native Python dictionaries, lists, and standard library modules without manual json manipulation.
"""

import os
import pprint
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import requests

from config.database import (
    create_task_booking,
    update_task_booking,
    query_task_bookings,
    record_live_event,
    get_system_counts,
    query_latest_events,
)

logger = logging.getLogger(__name__)

EXTERNAL_WEBHOOK_URL = os.getenv("EXTERNAL_WEBHOOK_URL")

# ==============================================================================
# MCP Tool Definitions (Declared as pure Python dictionaries)
# ==============================================================================

AVAILABLE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "alexa_create_booking",
        "description": "Create a new appointment, reservation, or service booking in the Alexa+ system. Writes directly to the SQL database and logs telemetry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short descriptive title for the booking (e.g. 'Dinner at Olive Garden', 'Doctor Consultation')",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Name of the person requesting or assigned to the booking",
                },
                "category": {
                    "type": "string",
                    "enum": ["doctor", "restaurant", "cab", "flight", "home_service", "general"],
                    "description": "Category of the booking",
                    "default": "general",
                },
                "scheduled_time": {
                    "type": "string",
                    "description": "Scheduled date-time string (e.g., '2026-10-15T19:00:00Z')",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed notes, party size, location, or special instructions",
                },
            },
            "required": ["title", "customer_name"],
        },
    },
    {
        "name": "alexa_update_booking_status",
        "description": "Update the lifecycle status of an existing booking or task in the database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "Unique UUID of the target booking record",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "confirmed", "in_progress", "completed", "cancelled"],
                    "description": "New status to apply",
                },
                "notes": {
                    "type": "string",
                    "description": "Reason or operational notes regarding this status transition",
                },
            },
            "required": ["booking_id", "status"],
        },
    },
    {
        "name": "alexa_query_tasks",
        "description": "Query tasks, bookings, and automations from the SQL database using status and category filters.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "pending", "confirmed", "in_progress", "completed", "cancelled"],
                    "description": "Filter by task status ('all' for no status filter)",
                    "default": "all",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of records to return (1-50)",
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "alexa_execute_automation",
        "description": "Trigger an automated smart workflow or device scene with database persistence and live telemetry streaming.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["smart_home_scene", "reminder_broadcast", "device_control", "system_sync"],
                    "description": "Type of automated action to execute",
                },
                "target_device_or_service": {
                    "type": "string",
                    "description": "Identifier of the device, room, or service",
                },
                "parameters": {
                    "type": "object",
                    "description": "Configuration parameters as a Python dictionary",
                    "default": {},
                },
                "notify_user": {
                    "type": "boolean",
                    "description": "Whether to dispatch an audible confirmation or notification",
                    "default": True,
                },
            },
            "required": ["action_type", "target_device_or_service"],
        },
    },
    {
        "name": "alexa_get_system_health",
        "description": "Retrieve system operational health, total tasks, pending bookings, and database statistics.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]

# ==============================================================================
# MCP Resources Definitions
# ==============================================================================

AVAILABLE_RESOURCES: List[Dict[str, Any]] = [
    {
        "uri": "alexa://bookings/active",
        "name": "Active Bookings & Tasks",
        "description": "Live snapshot of all pending and confirmed bookings in SQL",
        "mimeType": "text/plain",
    },
    {
        "uri": "alexa://events/stream",
        "name": "Live Event Stream Log",
        "description": "Recent 20 live telemetry and tool execution audit entries from SQL",
        "mimeType": "text/plain",
    },
    {
        "uri": "alexa://system/metrics",
        "name": "System Health and Database Metrics",
        "description": "Operational counts, task distributions, and database health metrics",
        "mimeType": "text/plain",
    },
]


# ==============================================================================
# Pure Python Tool Execution Functions
# ==============================================================================

def execute_create_booking(arguments: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a new booking record using Python dictionaries."""
    title = str(arguments.get("title", "")).strip()
    customer_name = str(arguments.get("customer_name", "")).strip()
    category = str(arguments.get("category", "general"))
    description = str(arguments.get("description", ""))
    scheduled_time_str = arguments.get("scheduled_time")

    if not title:
        raise ValueError("Field 'title' is required.")
    if not customer_name:
        raise ValueError("Field 'customer_name' is required.")

    scheduled_time = None
    if scheduled_time_str:
        try:
            clean_time_str = scheduled_time_str.replace("Z", "+00:00")
            scheduled_time = datetime.fromisoformat(clean_time_str)
        except Exception as exc:
            logger.warning(f"Could not parse scheduled_time: {exc}")

    metadata = {
        "customer_name": customer_name,
        "created_by": "alexa_mcp_agent",
        "source": "voice_interaction",
    }

    record = create_task_booking(
        title=f"{title} (for {customer_name})",
        category=category,
        status="pending",
        description=description,
        scheduled_time=scheduled_time,
        metadata=metadata,
        session_id=session_id,
    )

    webhook_status = "skipped"
    if EXTERNAL_WEBHOOK_URL:
        try:
            resp = requests.post(
                EXTERNAL_WEBHOOK_URL,
                json={"event": "BOOKING_CREATED", "data": record},
                timeout=3.0,
            )
            webhook_status = f"dispatched ({resp.status_code})"
        except Exception as err:
            webhook_status = f"failed ({err})"

    return {
        "success": True,
        "message": f"Successfully created booking '{record['title']}'.",
        "booking_id": record["id"],
        "status": record["status"],
        "scheduled_time": record["scheduled_time"],
        "webhook_dispatch": webhook_status,
        "record": record,
    }


def execute_update_booking_status(arguments: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
    """Update status of a booking in Python."""
    booking_id = str(arguments.get("booking_id", "")).strip()
    status = str(arguments.get("status", "")).strip().lower()
    notes = str(arguments.get("notes", ""))

    if not booking_id:
        raise ValueError("Field 'booking_id' is required.")
    if not status:
        raise ValueError("Field 'status' is required.")

    allowed_statuses = ["pending", "confirmed", "in_progress", "completed", "cancelled"]
    if status not in allowed_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {allowed_statuses}")

    patch = {"last_status_note": notes, "updated_via": "mcp_tool"} if notes else None
    updated = update_task_booking(
        booking_id=booking_id,
        status=status,
        description=notes if notes else None,
        metadata_patch=patch,
        session_id=session_id,
    )

    if not updated:
        return {
            "success": False,
            "error": f"Booking ID '{booking_id}' not found.",
        }

    return {
        "success": True,
        "message": f"Booking '{booking_id}' updated to status '{status}'.",
        "booking_id": booking_id,
        "new_status": status,
        "record": updated,
    }


def execute_query_tasks(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Query tasks from the SQL database using pure Python."""
    status_filter = arguments.get("status", "all")
    category_filter = arguments.get("category")
    limit = int(arguments.get("limit", 10))
    limit = max(1, min(limit, 50))

    query_status = None if status_filter == "all" else status_filter
    records = query_task_bookings(status=query_status, category=category_filter, limit=limit)

    return {
        "success": True,
        "count": len(records),
        "status_filter": status_filter,
        "category_filter": category_filter,
        "tasks": records,
    }


def execute_automation(arguments: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
    """Execute an automated action and persist in SQL using Python."""
    action_type = arguments.get("action_type")
    target = arguments.get("target_device_or_service")
    parameters = arguments.get("parameters", {})
    notify_user = arguments.get("notify_user", True)

    if not action_type or not target:
        raise ValueError("Both 'action_type' and 'target_device_or_service' are required.")

    task = create_task_booking(
        title=f"Automation: {action_type} on {target}",
        category="automation",
        status="completed",
        description=f"Automated action on '{target}'.",
        metadata={
            "action_type": action_type,
            "target": target,
            "parameters": parameters,
            "notify_user": notify_user,
        },
        session_id=session_id,
    )

    event = record_live_event(
        event_type="AUTOMATION_EXECUTED",
        details={
            "task_id": task["id"],
            "action_type": action_type,
            "target": target,
            "parameters": parameters,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        },
        session_id=session_id,
    )

    return {
        "success": True,
        "message": f"Automation '{action_type}' on '{target}' completed successfully.",
        "task_id": task["id"],
        "event_id": event["id"],
        "action_type": action_type,
        "target": target,
        "parameters": parameters,
        "status": "completed",
    }


def execute_get_system_health() -> Dict[str, Any]:
    """Return health metrics as a Python dictionary."""
    counts = get_system_counts()
    return {
        "success": True,
        "status": "healthy",
        "service": "alexa-mcp-flask",
        "metrics": counts,
    }


# ==============================================================================
# Master Tool Dispatcher
# ==============================================================================

def call_tool(tool_name: str, arguments: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
    """Dispatch tool call and return clean Python dictionary representation."""
    logger.info(f"Executing tool '{tool_name}' for session '{session_id}'")

    if tool_name == "alexa_create_booking":
        result = execute_create_booking(arguments, session_id=session_id)
    elif tool_name == "alexa_update_booking_status":
        result = execute_update_booking_status(arguments, session_id=session_id)
    elif tool_name == "alexa_query_tasks":
        result = execute_query_tasks(arguments)
    elif tool_name == "alexa_execute_automation":
        result = execute_automation(arguments, session_id=session_id)
    elif tool_name == "alexa_get_system_health":
        result = execute_get_system_health()
    else:
        raise ValueError(f"Unknown tool: '{tool_name}'")

    # Present formatted Python dictionary text
    return {
        "content": [
            {
                "type": "text",
                "text": pprint.pformat(result, sort_dicts=False),
            }
        ],
        "isError": not result.get("success", True),
    }


# ==============================================================================
# Master Resource Dispatcher
# ==============================================================================

def read_resource(uri: str) -> Dict[str, Any]:
    """Resolve and read MCP resource URI as formatted Python data."""
    logger.info(f"Reading MCP resource: {uri}")

    if uri == "alexa://bookings/active":
        bookings = query_task_bookings(status=None, limit=50)
        active_bookings = [b for b in bookings if b["status"] in ("pending", "confirmed", "in_progress")]
        data = {
            "resource": uri,
            "count": len(active_bookings),
            "data": active_bookings,
        }
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": pprint.pformat(data, sort_dicts=False),
                }
            ]
        }

    elif uri == "alexa://events/stream":
        events = query_latest_events(limit=20)
        data = {
            "resource": uri,
            "count": len(events),
            "data": events,
        }
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": pprint.pformat(data, sort_dicts=False),
                }
            ]
        }

    elif uri == "alexa://system/metrics":
        metrics = get_system_counts()
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "text/plain",
                    "text": pprint.pformat(metrics, sort_dicts=False),
                }
            ]
        }

    else:
        raise ValueError(f"Resource URI '{uri}' not found.")
