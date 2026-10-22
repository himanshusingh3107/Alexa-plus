"""Server-Sent Events (SSE) Route implementation written in pure Python.

Handles GET /sse for streamable HTTP connections (mimetype='text/event-stream'),
initial handshake, keep-alive pings, and real-time live database updates.
"""

import os
import time
import json
import uuid
import queue
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from flask import Blueprint, Response, request, stream_with_context
from config.database import query_latest_events, record_live_event, get_max_event_id

logger = logging.getLogger(__name__)

sse_bp = Blueprint("sse_bp", __name__)

# Thread-safe in-memory registry for active SSE client session queues
_session_lock = threading.Lock()
_active_sessions: Dict[str, queue.Queue] = {}

KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "15"))
DB_POLL_INTERVAL = int(os.getenv("DB_POLL_INTERVAL", "3"))


def register_session(session_id: str) -> queue.Queue:
    """Register a new active SSE session and its message queue."""
    q: queue.Queue = queue.Queue(maxsize=100)
    with _session_lock:
        _active_sessions[session_id] = q
    logger.info(f"SSE session registered: {session_id} (Total active: {len(_active_sessions)})")
    return q


def unregister_session(session_id: str) -> None:
    """Unregister an SSE session upon disconnect."""
    with _session_lock:
        if session_id in _active_sessions:
            del _active_sessions[session_id]
    logger.info(f"SSE session unregistered: {session_id} (Total active: {len(_active_sessions)})")


def push_to_session(session_id: str, event_name: str, data: Any) -> bool:
    """Push an SSE message to a specific session's queue."""
    with _session_lock:
        q = _active_sessions.get(session_id)

    if q:
        try:
            q.put_nowait({"event": event_name, "data": data})
            return True
        except queue.Full:
            logger.warning(f"Queue full for session {session_id}, dropping message.")
            return False
    return False


def broadcast_sse(event_name: str, data: Any) -> None:
    """Broadcast an SSE message to all connected sessions."""
    with _session_lock:
        sessions = list(_active_sessions.values())

    for q in sessions:
        try:
            q.put_nowait({"event": event_name, "data": data})
        except queue.Full:
            pass


def format_sse_message(event: str, data: Any) -> str:
    """Format payload according to the SSE standard specification in clean single-line JSON."""
    if isinstance(data, (dict, list)):
        data_str = json.dumps(data)
    else:
        data_str = str(data)

    return f"event: {event}\ndata: {data_str}\n\n"


def sse_event_stream(session_id: str, session_queue: queue.Queue):
    """Generator streaming events, keep-alive pings, and database updates."""
    logger.info(f"Starting SSE event stream generator for session: {session_id}")

    # Start from the current max event ID so historical events are not dumped upon connection
    last_db_event_id = get_max_event_id()

    try:
        # 1. Initial MCP handshake event: endpoint location for POST requests
        endpoint_uri = f"/messages?session_id={session_id}"
        yield format_sse_message("endpoint", endpoint_uri)

        # 2. Connection acknowledgment event
        welcome_payload = {
            "session_id": session_id,
            "server": "alexa-mcp-flask",
            "protocol_spec": "2025-11-25",
            "status": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield format_sse_message("connected", welcome_payload)

        last_ping_time = time.time()
        last_db_poll_time = time.time()

        while True:
            current_time = time.time()

            # A. Check and deliver pending queued messages for this session
            try:
                msg = session_queue.get(timeout=1.0)
                event_name = msg.get("event", "message")
                event_data = msg.get("data", {})
                yield format_sse_message(event_name, event_data)
            except queue.Empty:
                pass

            # B. Stream live database updates (SELECT queries)
            if current_time - last_db_poll_time >= DB_POLL_INTERVAL:
                try:
                    new_events = query_latest_events(after_id=last_db_event_id, session_id=session_id)
                    if new_events:
                        for evt in new_events:
                            yield format_sse_message("database_update", evt)
                            if evt["id"] > last_db_event_id:
                                last_db_event_id = evt["id"]
                except Exception as db_err:
                    logger.error(f"Error querying live database updates: {db_err}")
                last_db_poll_time = current_time

            # C. Send keep-alive pings
            if current_time - last_ping_time >= KEEP_ALIVE_INTERVAL:
                ping_payload = {
                    "type": "ping",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "session_id": session_id,
                }
                yield format_sse_message("ping", ping_payload)
                last_ping_time = current_time

    except GeneratorExit:
        logger.info(f"Client disconnected from SSE stream: {session_id}")
    except Exception as exc:
        logger.error(f"Unexpected error in SSE stream for {session_id}: {exc}", exc_info=True)
    finally:
        unregister_session(session_id)


@sse_bp.route("/sse", methods=["GET"])
def sse_endpoint():
    """GET /sse endpoint establishing streamable HTTP SSE connection."""
    client_session_id = request.args.get("session_id") or request.args.get("sessionId")
    session_id = client_session_id if client_session_id else str(uuid.uuid4())

    session_queue = register_session(session_id)

    response = Response(
        stream_with_context(sse_event_stream(session_id, session_queue)),
        mimetype="text/event-stream",
    )

    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"

    return response
