"""Python message handler for MCP over HTTP.

Processes requests using native Python data structures (dictionaries, lists, strings)
via Flask's request.get_json() and jsonify().
"""

import logging
from typing import Dict, Any, Optional

from flask import Blueprint, request, jsonify, Response
from services.external_tools import (
    AVAILABLE_TOOLS,
    AVAILABLE_RESOURCES,
    call_tool,
    read_resource,
)
from routes.sse_routes import push_to_session, broadcast_sse

logger = logging.getLogger(__name__)

message_bp = Blueprint("message_bp", __name__)

# Standard JSON-RPC error codes
RPC_PARSE_ERROR = -32700
RPC_INVALID_REQUEST = -32600
RPC_METHOD_NOT_FOUND = -32601
RPC_INVALID_PARAMS = -32602
RPC_INTERNAL_ERROR = -32603


def make_rpc_success(req_id: Any, result: Any) -> Dict[str, Any]:
    """Format successful response as a Python dictionary."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


def make_rpc_error(req_id: Any, code: int, message: str, data: Optional[Any] = None) -> Dict[str, Any]:
    """Format error response as a Python dictionary."""
    err = {
        "code": code,
        "message": message,
    }
    if data is not None:
        err["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": err,
    }


def handle_initialize(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle initialize handshake using a pure Python dictionary."""
    client_protocol = params.get("protocolVersion", "2024-11-05")
    logger.info(f"Initialize handshake received (client protocol: {client_protocol})")

    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": True},
            "resources": {"subscribe": True, "listChanged": True},
            "prompts": {"listChanged": False},
            "logging": {},
        },
        "serverInfo": {
            "name": "alexa-mcp-flask",
            "version": "1.0.0",
        },
        "instructions": "Production MCP Server for Alexa+ Hackathon. Built 100% in Python.",
    }


def process_single_request(payload: Dict[str, Any], session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Process request payload directly as a Python dictionary."""
    if not isinstance(payload, dict):
        return make_rpc_error(None, RPC_INVALID_REQUEST, "Expected a valid dictionary payload.")

    if payload.get("jsonrpc") != "2.0":
        return make_rpc_error(payload.get("id"), RPC_INVALID_REQUEST, "Invalid protocol version.")

    method = payload.get("method")
    req_id = payload.get("id")
    params = payload.get("params", {}) or {}

    if not method or not isinstance(method, str):
        return make_rpc_error(req_id, RPC_INVALID_REQUEST, "Missing method name.")

    is_notification = req_id is None

    try:
        if method == "initialize":
            res = handle_initialize(params)
            return make_rpc_success(req_id, res)

        elif method == "notifications/initialized":
            logger.info(f"Client initialized notification acknowledged (session: {session_id}).")
            if is_notification:
                return None
            return make_rpc_success(req_id, {})

        elif method == "ping":
            return make_rpc_success(req_id, {})

        elif method == "tools/list":
            return make_rpc_success(req_id, {"tools": AVAILABLE_TOOLS})

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            if not tool_name:
                return make_rpc_error(req_id, RPC_INVALID_PARAMS, "Missing tool 'name'.")

            tool_result = call_tool(tool_name, tool_args, session_id=session_id)

            sse_data = {
                "event": "TOOL_INVOKED",
                "tool": tool_name,
                "session_id": session_id,
                "is_error": tool_result.get("isError", False),
            }
            if session_id:
                push_to_session(session_id, "tool_execution", sse_data)
            else:
                broadcast_sse("tool_execution", sse_data)

            return make_rpc_success(req_id, tool_result)

        elif method == "resources/list":
            return make_rpc_success(req_id, {"resources": AVAILABLE_RESOURCES})

        elif method == "resources/read":
            uri = params.get("uri")
            if not uri:
                return make_rpc_error(req_id, RPC_INVALID_PARAMS, "Missing resource 'uri'.")

            resource_result = read_resource(uri)
            return make_rpc_success(req_id, resource_result)

        else:
            logger.warning(f"Unknown method requested: {method}")
            return make_rpc_error(req_id, RPC_METHOD_NOT_FOUND, f"Method '{method}' not found.")

    except ValueError as err:
        return make_rpc_error(req_id, RPC_INVALID_PARAMS, str(err))
    except Exception as exc:
        logger.error(f"Error handling method {method}: {exc}", exc_info=True)
        return make_rpc_error(req_id, RPC_INTERNAL_ERROR, str(exc))


@message_bp.route("/messages", methods=["POST"])
def messages_endpoint():
    """POST /messages endpoint handling Python dictionaries via Flask."""
    session_id = (
        request.args.get("session_id")
        or request.args.get("sessionId")
        or request.headers.get("X-Session-ID")
    )

    # Pure Python: Flask parses request body directly into Python dict or list
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(make_rpc_error(None, RPC_PARSE_ERROR, "Invalid or empty payload.")), 400

    # Batch support
    if isinstance(payload, list):
        if not payload:
            return jsonify(make_rpc_error(None, RPC_INVALID_REQUEST, "Empty list.")), 400

        responses = []
        for req in payload:
            res = process_single_request(req, session_id=session_id)
            if res is not None:
                responses.append(res)

        if not responses:
            return Response(status=204)
        return jsonify(responses), 200

    # Single request
    single_res = process_single_request(payload, session_id=session_id)
    if single_res is None:
        return Response(status=204)

    return jsonify(single_res), 200
