<p align="center">
  <img src="https://img.shields.io/badge/Amazon-Alexa%2B-00CAFF?style=for-the-badge&logo=amazon-alexa&logoColor=white" alt="Alexa+" />
  <img src="https://img.shields.io/badge/MCP-Model%20Context%20Protocol-6C3483?style=for-the-badge" alt="MCP" />
  <img src="https://img.shields.io/badge/Gemini-AI%20Powered-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/AWS-Lambda%20%7C%20SAM-FF9900?style=for-the-badge&logo=amazon-aws&logoColor=white" alt="AWS" />
</p>

# 🧠 Alexa+ — The Context-Aware, Proactive AI Assistant

> **Amazon Developer Hackathon 2026 — Alexa+ Platform Track Submission**

**Alexa+** is an advanced, context-aware, proactive AI assistant that transcends traditional rigid Alexa skills. Instead of mapping utterances to fixed commands, Alexa+ fuses **Large Language Models (LLMs)**, a **Model Context Protocol (MCP) server**, and a **contextual memory engine** to deliver truly intelligent, personalized voice interactions.

---

## 🏆 Key Innovation: Why Alexa+ is Different

| Traditional Alexa Skill | Alexa+ |
|---|---|
| Rigid intent mapping → fixed response | Free-form speech → LLM reasoning → dynamic tool selection |
| Stateless single-shot commands | Persistent memory across sessions — remembers preferences, history, context |
| Developer defines every dialog flow | AI dynamically constructs responses using MCP tools |
| No proactive engagement | Proactive notifications based on user patterns and events |
| Skill-per-service architecture | Single unified skill with dynamic tool routing to any backend |

---

## ✨ Feature Highlights

### 🔄 Dynamic Tool Routing via MCP
Instead of hardcoding business logic per intent, Alexa+ exposes backend capabilities as **MCP tools**. The LLM reasons over user input and dynamically selects the right tool — booking appointments, controlling smart home devices, querying databases — all through natural conversation.

### 🧠 Contextual Memory Engine
A persistent SQLite-backed memory layer stores:
- **User profiles** and display names
- **Preferences** (favorite restaurants, preferred temperature, doctor names)
- **Conversation history** across sessions
- **Interaction statistics** for pattern learning

The LLM receives this context every turn, enabling responses like: *"Welcome back, Alex! Last time you asked about your dental appointment — it's confirmed for Thursday."*

### 🔔 Proactive Automations
Alexa+ doesn't just wait for commands — it can:
- Push notifications when booking statuses change
- Trigger smart home scenes based on user patterns
- Send reminders and follow-up messages via the Alexa Proactive Events API

### 🌐 Multimodal Bridge (MCP + LLM + ASK)
The architecture bridges three protocols:
1. **Alexa Skills Kit (ASK)** — handles voice I/O and device communication
2. **Model Context Protocol (MCP)** — standardized tool interface for AI agents
3. **Gemini LLM** — reasoning engine that understands intent and orchestrates tools

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    User's Alexa Device                       │
│              "Alexa, ask Alexa Plus to..."                   │
└──────────────────────┬───────────────────────────────────────┘
                       │  Voice → ASK
                       ▼
┌──────────────────────────────────────────────────────────────┐
│               AWS Lambda (lambda_handler.py)                 │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │           Alexa Skills Kit (ASK) SDK                    │ │
│  │  • Intent handlers (Launch, Booking, SmartHome, etc.)   │ │
│  │  • Session attribute management                         │ │
│  │  • Multi-turn dialog support                            │ │
│  └────────────────────┬────────────────────────────────────┘ │
│                       ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │           LLM Orchestrator (Gemini 3.8 Flash)           │ │
│  │  • Understands natural language intent                   │ │
│  │  • Selects appropriate MCP tools                         │ │
│  │  • Generates conversational responses                    │ │
│  │  • Receives user context from memory                     │ │
│  └────────────────────┬────────────────────────────────────┘ │
│                       ▼                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Memory Engine│  │ MCP Tool     │  │ Proactive Events  │  │
│  │ (SQLite/     │  │ Dispatcher   │  │ Bridge            │  │
│  │  Turso DB)   │  │              │  │                   │  │
│  └──────────────┘  └──────┬───────┘  └───────────────────┘  │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                 MCP Server (mcp_server.py)                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Tools:                                                │  │
│  │  • alexa_create_booking    • alexa_query_tasks         │  │
│  │  • alexa_update_booking    • alexa_execute_automation  │  │
│  │  • alexa_get_system_health • memory_fetch              │  │
│  │  • memory_save_preference  • proactive_notify          │  │
│  │  • context_summary                                     │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │  Resources:                                            │  │
│  │  • alexa://bookings/active  • alexa://events/stream    │  │
│  │  • alexa://system/metrics                              │  │
│  ├────────────────────────────────────────────────────────┤  │
│  │  Prompts:                                              │  │
│  │  • alexa-assistant         • booking-helper            │  │
│  └────────────────────────────────────────────────────────┘  │
│                           │                                  │
│                    SQLAlchemy ORM                             │
│                    ┌──────────┐                              │
│                    │  SQLite  │                              │
│                    │  Database│                              │
│                    └──────────┘                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
alexa-mcp-flask/
├── app.py                    # Flask MCP HTTP server (SSE + JSON-RPC transport)
├── mcp_server.py             # Standalone MCP server (stdio transport for LLM agents)
├── lambda_handler.py         # AWS Lambda entry point for Alexa skill requests
├── memory_engine.py          # Contextual memory engine (SQLite persistence)
├── client.py                 # Python MCP client for testing
├── config/
│   └── database.py           # SQLAlchemy models, engine, session management
├── routes/
│   ├── message_routes.py     # JSON-RPC message handler (MCP protocol)
│   └── sse_routes.py         # Server-Sent Events for real-time streaming
├── services/
│   └── external_tools.py     # MCP tool definitions and execution logic
├── skill/
│   ├── skill.json            # Alexa Skill Package manifest
│   └── interactionModels/
│       └── custom/
│           └── en-US.json    # Alexa Interaction Model (intents, slots, dialogs)
├── template.yaml             # AWS SAM deployment template
├── samconfig.toml            # SAM CLI configuration
├── Dockerfile                # Container deployment
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
└── README.md                 # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **AWS CLI** configured with credentials
- **ASK CLI** (Alexa Skills Kit CLI) — `npm install -g ask-cli`
- **AWS SAM CLI** — `pip install aws-sam-cli`
- **Gemini API Key** — Get one at [aistudio.google.com](https://aistudio.google.com)
- **ngrok** (for local testing) — [ngrok.com](https://ngrok.com)

### 1. Clone & Install

```bash
git clone https://github.com/your-team/alexa-plus.git
cd alexa-plus/alexa-mcp-flask

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys:
#   GEMINI_API_KEY=your_gemini_api_key
#   ALEXA_SKILL_ID=amzn1.ask.skill.xxxxx
```

### 3. Local Development (MCP Server)

```bash
# Start the Flask-based MCP HTTP server
python app.py

# In another terminal, test with the Python client
python client.py

# Or run the stdio MCP server (for direct LLM integration)
python mcp_server.py
```

### 4. Local Alexa Skill Testing (with ngrok)

```bash
# Start Flask server
python app.py

# In another terminal, expose via ngrok
ngrok http 5000

# Copy the HTTPS URL from ngrok and set it as your Alexa skill endpoint
# In the Alexa Developer Console → Endpoint → HTTPS → paste URL + /alexa
```

### 5. Deploy to AWS Lambda (Production)

```bash
# Build and deploy with SAM
sam build
sam deploy --guided

# The output will show your Lambda function ARN
# Copy it to your Alexa skill endpoint configuration
```

---

## 🧪 Testing

### Test MCP Server Locally

```bash
# Run the interactive client tester
python client.py
```

This will:
1. ✅ Connect to the MCP server via SSE
2. ✅ Perform protocol handshake
3. ✅ List available tools
4. ✅ Create a test booking
5. ✅ Execute a smart home automation
6. ✅ Query database records
7. ✅ Check system health

### Test Memory Engine

```bash
python memory_engine.py
```

### Test Lambda Handler Locally

```bash
# Requires GEMINI_API_KEY in .env
python lambda_handler.py
```

### Test with ASK CLI

```bash
# Simulate Alexa requests
ask dialog --locale en-US
> open alexa plus
> book a doctor appointment for Alex tomorrow at 3pm
> what's on my schedule
> turn on the living room lights
> what do you remember about me
```

---

## 🔧 Configuration

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Google Gemini API key for LLM orchestration |
| `DATABASE_URL` | `sqlite:///alexa_mcp.db` | SQLAlchemy database URL |
| `ALEXA_SKILL_ID` | — | Your Alexa Skill ID for request validation |
| `ALEXA_CLIENT_ID` | — | Alexa client ID for Proactive Events API |
| `ALEXA_CLIENT_SECRET` | — | Alexa client secret for Proactive Events API |
| `FLASK_PORT` | `5000` | Local server port |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `KEEP_ALIVE_INTERVAL` | `15` | SSE keep-alive ping interval (seconds) |
| `DB_POLL_INTERVAL` | `3` | Live database polling interval (seconds) |

---

## 🤖 How the LLM Orchestration Works

```
User: "Book a dental cleaning for Alex next Thursday"
                    │
                    ▼
        ┌───────────────────┐
        │  Intent Handler   │
        │  (ASK SDK)        │
        │  Extracts slots   │
        └────────┬──────────┘
                 │
                 ▼
        ┌───────────────────┐
        │  Memory Engine    │  ← Loads: "Alex prefers Dr. Smith, last dental was 6 months ago"
        │  (Context Load)   │
        └────────┬──────────┘
                 │
                 ▼
        ┌───────────────────┐
        │  LLM Orchestrator │  ← System prompt + user context + available tools
        │  (Gemini 3.8)     │  → Decides: call alexa_create_booking with extracted args
        └────────┬──────────┘
                 │
                 ▼
        ┌───────────────────┐
        │  MCP Tool Call    │  → Creates booking in SQLite database
        │  (create_booking) │  → Logs telemetry event
        └────────┬──────────┘
                 │
                 ▼
        ┌───────────────────┐
        │  Memory Save      │  ← Saves this interaction to conversation history
        │  + Response Gen   │  → "Done! I've booked your dental cleaning with Dr. Smith
        └───────────────────┘     for next Thursday. Want me to set a reminder?"
```

---

## 📊 MCP Tools Reference

| Tool | Description | Key Arguments |
|---|---|---|
| `alexa_create_booking` | Create appointments/reservations | title, customer_name, category, scheduled_time |
| `alexa_update_booking_status` | Update booking lifecycle status | booking_id, status, notes |
| `alexa_query_tasks` | Query tasks with filters | status, category, limit |
| `alexa_execute_automation` | Trigger smart home / automation workflows | action_type, target, parameters |
| `alexa_get_system_health` | System diagnostics and metrics | — |
| `memory_fetch` | Retrieve user profile and history | user_id |
| `memory_save_preference` | Save user preferences | user_id, key, value, category |
| `proactive_notify` | Push proactive notifications | user_id, message, priority |
| `context_summary` | Full contextual summary for LLM | user_id |

---

## 🏛️ Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Voice Interface** | Alexa Skills Kit (ASK) | Voice I/O, NLU, device management |
| **Runtime** | AWS Lambda (Python 3.12) | Serverless execution |
| **AI Engine** | Google Gemini 3.8 Flash | Natural language understanding & generation |
| **Protocol** | Model Context Protocol (MCP) | Standardized AI ↔ Tool interface |
| **Transport** | HTTP/SSE + stdio | Real-time streaming + subprocess IPC |
| **Database** | SQLite / SQLAlchemy ORM | Persistent storage with migrations |
| **Web Framework** | Flask 3.x | HTTP server for MCP transport |
| **Deployment** | AWS SAM / Docker | Infrastructure as code |

---

## 🛣️ Roadmap

- [x] MCP Server with HTTP/SSE transport
- [x] MCP Server with stdio transport  
- [x] SQLAlchemy database with task/booking management
- [x] Real-time SSE event streaming
- [x] Alexa Custom Skill interaction model
- [x] AWS Lambda handler with ASK SDK
- [x] LLM Orchestration with Gemini 3.8 Flash
- [x] Contextual Memory Engine
- [x] Proactive Events API bridge
- [x] AWS SAM deployment template
- [ ] DynamoDB production adapter
- [ ] Multi-language support (es-ES, de-DE)
- [ ] APL visual responses for Echo Show
- [ ] Routine Suggestions API integration
- [ ] Voice biometric personalization

---

## 👥 Team

Built with ❤️ for the **Amazon Developer Hackathon 2026**

---

## 📄 License

This project is built for the Amazon Developer Hackathon and is available under the [MIT License](LICENSE).

---

<p align="center">
  <b>Alexa+ — When AI meets voice, conversation becomes intelligence.</b>
</p>
