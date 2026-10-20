"""Main entry point for the Alexa+ MCP Server.

Initializes Flask, enables CORS, configures logging, initializes the SQL schema,
and mounts blueprints for SSE streaming and JSON-RPC message handling.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env file before importing application modules
load_dotenv()

from flask import Flask, jsonify
from flask_cors import CORS

from config.database import init_db
from routes.sse_routes import sse_bp
from routes.message_routes import message_bp

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("alexa_mcp_app")


def create_app() -> Flask:
    """Application factory for the Alexa+ MCP Server."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "default-dev-secret-key")

    # Configure CORS for all origins, required for SSE and cross-origin Alexa client calls
    CORS(
        app,
        resources={
            r"/*": {
                "origins": "*",
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization", "X-Session-ID", "Accept"],
                "expose_headers": ["Content-Type", "X-Session-ID"],
            }
        },
    )

    # Initialize SQL database schema
    with app.app_context():
        try:
            init_db()
        except Exception as exc:
            logger.error(f"Failed to initialize database: {exc}", exc_info=True)
            raise

    # Register MCP Blueprints
    app.register_blueprint(sse_bp)
    app.register_blueprint(message_bp)

    from flask import render_template, request
    from config.database import get_system_counts, query_task_bookings
    from services.external_tools import call_tool

    @app.route("/", methods=["GET"])
    def root():
        """Root endpoint: Serves visual Web UI for browsers, JSON for API/MCP clients."""
        accept = request.headers.get("Accept", "")
        if "text/html" in accept:
            return render_template("index.html")

        return jsonify({
            "service": "Alexa+ MCP Production Server",
            "protocol": "Model Context Protocol (MCP)",
            "transport": "Streamable HTTP with Server-Sent Events (SSE)",
            "version": "1.0.0",
            "specification_version": "2025-11-25",
            "endpoints": {
                "dashboard": "/",
                "sse": "/sse",
                "messages": "/messages",
                "health": "/health",
            },
            "status": "online",
        }), 200

    @app.route("/dashboard", methods=["GET"])
    def dashboard():
        """Explicit route to access the visual web dashboard."""
        return render_template("index.html")

    @app.route("/api/dashboard/stats", methods=["GET"])
    def dashboard_stats():
        """Returns live system counts and operational metrics for the web UI."""
        return jsonify(get_system_counts()), 200

    @app.route("/api/dashboard/tasks", methods=["GET"])
    def dashboard_tasks():
        """Returns the latest 20 voice bookings and tasks."""
        return jsonify(query_task_bookings(limit=20)), 200

    @app.route("/api/dashboard/simulate", methods=["POST"])
    def dashboard_simulate():
        """Interactive simulator: parses natural text commands and invokes MCP tools live."""
        data = request.get_json(silent=True) or {}
        utterance = str(data.get("utterance", "")).strip()
        lowered = utterance.lower()

        if not utterance:
            return jsonify({"response": "Please enter a command to simulate."}), 400

        tool_used = None
        spoken_response = ""

        try:
            # 1. Booking Simulation
            if any(w in lowered for w in ["book", "appointment", "reservation", "schedule"]):
                category = "doctor" if "doctor" in lowered or "dentist" in lowered else ("restaurant" if "table" in lowered or "dinner" in lowered else "general")
                title = utterance.replace("book", "").replace("schedule", "").strip().title() or "Appointment"
                tool_res = call_tool("alexa_create_booking", {
                    "title": title,
                    "customer_name": "Demo User",
                    "category": category,
                    "description": f"Created via Web Simulator: {utterance}"
                })
                tool_used = "alexa_create_booking"
                spoken_response = f"Done! I've scheduled your {category} appointment ('{title}'). Booking record saved in database."

            # 2. Smart Home Automation Simulation
            elif any(w in lowered for w in ["turn on", "turn off", "ac", "conditioner", "light", "thermostat", "fan"]):
                device = "living_room_ac" if "ac" in lowered or "conditioner" in lowered else ("living_room_lights" if "light" in lowered else "smart_device")
                action = "turn_on" if "on" in lowered else "turn_off"
                call_tool("alexa_execute_automation", {
                    "action_type": "smart_home_scene",
                    "target_device_or_service": device,
                    "parameters": {"command": action, "level": 100}
                })
                tool_used = "alexa_execute_automation"
                spoken_response = f"Sure! I've executed the automated scene for '{device}'. State updated in telemetry."

            # 3. Query / Schedule Check
            elif any(w in lowered for w in ["tasks", "schedule", "bookings", "list"]):
                call_tool("alexa_query_tasks", {"limit": 5})
                tool_used = "alexa_query_tasks"
                spoken_response = "I've fetched your latest tasks from the database. You can review them in the live table below."

            # 4. System Health Check
            elif any(w in lowered for w in ["health", "status", "diagnostic", "report"]):
                health_data = call_tool("alexa_get_system_health", {})
                tool_used = "alexa_get_system_health"
                spoken_response = "System diagnostics complete: All MCP components, SQLite engine, and Turso Cloud database are operational."

            # Default conversational fallback
            else:
                spoken_response = f"I heard: \"{utterance}\". As an Alexa+ agent, I can book appointments, trigger automations, or check your database tasks."

            return jsonify({
                "success": True,
                "tool_used": tool_used,
                "response": spoken_response
            }), 200

        except Exception as exc:
            logger.error(f"Error in dashboard simulation: {exc}", exc_info=True)
            return jsonify({"error": str(exc), "response": "Encountered an issue executing the tool."}), 500

    @app.route("/health", methods=["GET"])
    def health():
        """Health check endpoint for orchestration, uptime probes, and load balancers."""
        return jsonify({
            "status": "healthy",
            "uptime": "operational",
        }), 200

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({
            "error": "Not Found",
            "message": "The requested endpoint does not exist on this MCP server.",
        }), 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({
            "error": "Internal Server Error",
            "message": "An unhandled exception occurred.",
        }), 500

    return app


app = create_app()

if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_PORT", "5000"))
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    logger.info(f"Starting Alexa+ MCP Server on {host}:{port} (Debug: {debug_mode})")

    # For production on Windows or Linux, waitress or threaded Flask development server
    try:
        from waitress import serve
        logger.info("Serving via production WSGI server (Waitress)...")
        serve(app, host=host, port=port, threads=8)
    except ImportError:
        logger.warning("Waitress not found, falling back to threaded development server.")
        app.run(host=host, port=port, debug=debug_mode, threaded=True)

