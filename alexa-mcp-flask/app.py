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

    @app.route("/", methods=["GET"])
    def root():
        """Root metadata endpoint providing server info and MCP endpoints."""
        return jsonify({
            "service": "Alexa+ MCP Production Server",
            "protocol": "Model Context Protocol (MCP)",
            "transport": "Streamable HTTP with Server-Sent Events (SSE)",
            "version": "1.0.0",
            "specification_version": "2025-11-25",
            "endpoints": {
                "sse": "/sse",
                "messages": "/messages",
                "health": "/health",
            },
            "status": "online",
        }), 200

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

