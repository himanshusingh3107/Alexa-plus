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
    from services.agent_orchestrator import AgenticOrchestrator

    # Initialize agent orchestrator
    agent_orchestrator = AgenticOrchestrator(user_id="default_alexa_user")

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

    @app.route("/presentation", methods=["GET"])
    def presentation():
        """Presentation slide deck and teleprompter for hackathon video recording."""
        return render_template("presentation.html")

    @app.route("/api/dashboard/stats", methods=["GET"])
    def dashboard_stats():
        """Returns live system counts and operational metrics for the web UI."""
        return jsonify(get_system_counts()), 200

    @app.route("/api/dashboard/tasks", methods=["GET"])
    def dashboard_tasks():
        """Returns the latest 20 voice bookings and tasks."""
        return jsonify(query_task_bookings(limit=20)), 200

    @app.route("/api/dashboard/reset", methods=["POST"])
    def dashboard_reset():
        """Reset all demo tasks, bookings, event logs, and conversation history."""
        try:
            from config.database import reset_database_data
            result = reset_database_data()
            return jsonify(result), 200
        except Exception as exc:
            logger.error(f"Error resetting database: {exc}", exc_info=True)
            return jsonify({"error": str(exc), "success": False}), 500

    @app.route("/api/dashboard/simulate", methods=["POST"])
    def dashboard_simulate():
        """Interactive simulator: parses natural speech/Hinglish/English commands and invokes MCP tools live via AgenticOrchestrator."""
        data = request.get_json(silent=True) or {}
        utterance = str(data.get("utterance", "")).strip()

        if not utterance:
            return jsonify({"response": "Please enter a command to simulate."}), 400

        try:
            result = agent_orchestrator.process_utterance(utterance, session_id="web-dashboard-session")
            return jsonify({
                "success": result.get("success", True),
                "tool_used": result.get("tool_used"),
                "response": result.get("response", ""),
                "thought": result.get("thought"),
            }), 200

        except Exception as exc:
            logger.error(f"Error in dashboard simulation: {exc}", exc_info=True)
            return jsonify({"error": str(exc), "response": "Encountered an issue executing the agent."}), 500

    @app.route("/api/transcribe", methods=["POST"])
    def transcribe_audio():
        """Transcribe uploaded voice audio using Google Gemini Multimodal model."""
        if "audio" not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files["audio"]
        audio_bytes = audio_file.read()
        mime_type = audio_file.content_type or "audio/webm"

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
            prompt = (
                "Transcribe this spoken voice command or question into accurate text. "
                "Accurately recognize Indian English, Hindi, and Hinglish phrases (e.g. 'andhera hai', 'lights band karo', 'turn on AC'). "
                "Return ONLY the plain transcript text with no extra commentary or tags."
            )
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    prompt,
                ],
            )
            transcript = (response.text or "").strip()
            return jsonify({"success": True, "transcript": transcript}), 200
        except Exception as exc:
            logger.error(f"Google Gemini audio transcription error: {exc}", exc_info=True)
            return jsonify({"error": str(exc)}), 500

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
