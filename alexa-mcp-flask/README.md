# Alexa+ MCP Server (Production-Ready)

A complete, production-ready **Model Context Protocol (MCP)** server built with **Python & Flask** adhering strictly to **MCP Specification (2025-11-25 / 2024-11-05)** over **Streamable HTTP (Server-Sent Events)** and **JSON-RPC 2.0**.

Designed specifically for the **Alexa+ Hackathon** to empower voice-enabled AI agents with real-time tool execution, persistent SQL state management, live telemetry streaming, and smart home automation workflows.

---

## 🌟 Key Features

- **Streamable HTTP Transport (SSE)**: Full `GET /sse` implementation delivering initial `endpoint` discovery events, keep-alive heartbeat pings, and real-time SQL database update streams.
- **JSON-RPC 2.0 Execution**: Compliant `POST /messages` handler supporting `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, and `ping`.
- **SQL Persistence**: SQLite (default zero-config) and PostgreSQL support powered by SQLAlchemy with thread-safe connection pooling and automatic schema initialization.
- **Specialized Alexa+ Tools**:
  - `alexa_create_booking`: Multi-category appointment & service reservation management with external webhook dispatch.
  - `alexa_update_booking_status`: Real-time lifecycle transition tracking (`pending` -> `confirmed` -> `completed`).
  - `alexa_query_tasks`: SQL `SELECT` querying with flexible category/status filtering.
  - `alexa_execute_automation`: Smart home and device automation scenes with telemetry audit logging.
  - `alexa_get_system_health`: Live operational telemetry and task statistics.
- **Dynamic MCP Resources**:
  - `alexa://bookings/active`: Live snapshot of pending and confirmed bookings.
  - `alexa://events/stream`: Live audit trail of tool invocations and system actions.
  - `alexa://system/metrics`: System health, total counts, and task distributions.
- **Production Hardened**: Comprehensive CORS policies, structured stdout logging, standard JSON-RPC error codes (`-32700`, `-32600`, `-32601`, `-32602`, `-32603`), and Waitress WSGI production server support.

---

## 📁 Project Directory Structure

```
alexa-mcp-flask/
├── config/
│   └── database.py          # SQL Database connection, schema setup & query helpers
├── routes/
│   ├── sse_routes.py        # GET /sse (Streamable HTTP, text/event-stream)
│   └── message_routes.py    # POST /messages (JSON-RPC 2.0 tool execution)
├── services/
│   └── external_tools.py    # Specialized task/tool execution logic & external API hooks
├── .env                     # Environment variables configuration
├── requirements.txt         # Production Python dependencies
├── app.py                   # Main entry point with CORS, logging & blueprints
└── README.md                # Documentation & testing walkthrough
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.10+ installed on your system.

### 2. Setup Virtual Environment & Install Dependencies
Navigate into the `alexa-mcp-flask` directory:

```bash
cd alexa-mcp-flask

# Create virtual environment
python -m venv venv

# Activate on Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Or on Linux / macOS:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
A default `.env` file is already included. You can customize the settings if needed:

```ini
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
DATABASE_URL=sqlite:///alexa_mcp.db
KEEP_ALIVE_INTERVAL=15
DB_POLL_INTERVAL=3
LOG_LEVEL=INFO
```

### 4. Run the Server
Launch using Python (Waitress WSGI is used automatically in production):

```bash
python app.py
```

The server will initialize the SQLite database (`alexa_mcp.db`) and listen on `http://127.0.0.1:5000`.

---

## 🐍 100% Pure Python Usage (No JSON Needed!)

If you do not want to deal with raw JSON or curl commands, you can do **everything in Python**:

### 1. Test and Interact via Python (`client.py`)
Run the interactive Python client:

```bash
python client.py
```

This runs a full end-to-end Python script that:
- Connects to the server over SSE streaming in the background
- Calls `client.create_booking(...)` using standard Python function arguments
- Calls `client.execute_automation(...)` to trigger smart home tasks
- Queries the SQL database with `client.query_tasks(...)`
- Prints friendly, human-readable Python messages (all JSON is handled automatically behind the scenes!)

### 2. Connect to Git via Python (`git_setup.py`)
To push your code to your new GitHub/GitLab repository without command-line hassle:

```bash
python git_setup.py
```
It will ask for your repository URL and automatically stage, commit, and push your project!

---

## 📡 Advanced Protocol Inspection (Optional cURL Guide)

If you wish to inspect the underlying HTTP/JSON-RPC protocol directly:

Open a new terminal window to test each endpoint.

### 1. Health & Server Info
```bash
curl -X GET http://127.0.0.1:5000/health
```

### 2. Initiate SSE Stream (`GET /sse`)
Start the long-lived SSE stream to observe the initial handshake, keep-alive pings, and database events:

```bash
curl -N -H "Accept: text/event-stream" http://127.0.0.1:5000/sse
```

**Expected SSE Output:**
```
event: endpoint
data: /messages?session_id=648f5733-1491-4cf4-916c-e4ec8f0851ec

event: connected
data: {"session_id": "648f5733-1491-4cf4-916c-e4ec8f0851ec", "server": "alexa-mcp-flask", ...}

event: ping
data: {"type": "ping", "timestamp": "...", "session_id": "..."}
```

---

### 3. MCP Handshake (`initialize`)
Send an initialization payload to `/messages`:

```bash
curl -X POST http://127.0.0.1:5000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {
        "name": "AlexaPlusClient",
        "version": "1.0.0"
      }
    }
  }'
```

---

### 4. Discover Available Tools (`tools/list`)
Query the available tool schemas defined on the server:

```bash
curl -X POST http://127.0.0.1:5000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
  }'
```

---

### 5. Execute Tool: Create a Booking (`tools/call`)
Call `alexa_create_booking` to insert a booking and stream telemetry:

```bash
curl -X POST http://127.0.0.1:5000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "alexa_create_booking",
      "arguments": {
        "title": "Dentist Checkup",
        "customer_name": "Sarah Connor",
        "category": "doctor",
        "scheduled_time": "2026-10-20T10:30:00Z",
        "description": "Routine dental cleaning and checkup."
      }
    }
  }'
```

Notice the SSE stream in your other terminal immediately receives a `database_update` and `tool_execution` event!

---

### 6. Execute Tool: Smart Automation (`tools/call`)
Trigger an automated workflow:

```bash
curl -X POST http://127.0.0.1:5000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "alexa_execute_automation",
      "arguments": {
        "action_type": "smart_home_scene",
        "target_device_or_service": "living_room_climate",
        "parameters": {
          "temperature_f": 72,
          "mode": "auto"
        },
        "notify_user": true
      }
    }
  }'
```

---

### 7. Read MCP Resources (`resources/read`)
Inspect active bookings directly through the MCP resource resolver:

```bash
curl -X POST http://127.0.0.1:5000/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 5,
    "method": "resources/read",
    "params": {
      "uri": "alexa://bookings/active"
    }
  }'
```

---

## 🎙️ Alexa+ Hackathon Agent Integration

To connect your Alexa+ Voice Agent or MCP client (e.g. Claude Desktop, OpenRouter, LangChain/LlamaIndex agents) to this server over SSE:

```json
{
  "mcpServers": {
    "alexa-plus-assistant": {
      "url": "http://127.0.0.1:5000/sse"
    }
  }
}
```

The client will connect to `/sse`, receive the endpoint discovery URL (`/messages?session_id=...`), perform the standard initialization handshake, and gain immediate access to all tools and database streaming resources!

