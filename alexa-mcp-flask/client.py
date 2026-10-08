"""Alexa+ MCP Pure Python Client & Interactive Tester.

Built 100% in Python. No JSON imports, no manual JSON encoding or decoding.
Work directly with standard Python functions, dictionaries, and lists.
"""

import ast
import time
import threading
from typing import Optional, Dict, Any, List
import requests


class AlexaMCPClient:
    """Pure Python client for the Alexa+ MCP Server."""

    def __init__(self, base_url: str = "http://127.0.0.1:5000"):
        self.base_url = base_url.rstrip("/")
        self.session_id: Optional[str] = None
        self.messages_url: str = f"{self.base_url}/messages"
        self._request_counter = 0
        self._listening = False
        self._listener_thread: Optional[threading.Thread] = None

    def _next_id(self) -> int:
        self._request_counter += 1
        return self._request_counter

    def _parse_python_data(self, text_content: str) -> Any:
        """Parse Python formatted dictionary string safely using ast.literal_eval."""
        try:
            return ast.literal_eval(text_content)
        except Exception:
            return {"raw_output": text_content}

    def _send_rpc(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Internal helper: sends Python dictionaries directly using requests."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        url = self.messages_url
        if self.session_id:
            url = f"{self.base_url}/messages?session_id={self.session_id}"

        response = requests.post(url, json=payload, timeout=10.0)
        response.raise_for_status()

        if response.status_code == 204 or not response.content:
            return {}

        res_data = response.json()
        if "error" in res_data:
            err = res_data["error"]
            raise RuntimeError(f"Server Error [{err.get('code')}]: {err.get('message')}")

        return res_data.get("result", {})

    # =========================================================================
    # 1. Connection & Live Event Streaming (Pure Python SSE)
    # =========================================================================

    def start_listening(self) -> None:
        """Start listening to live database updates and keep-alive pings in background."""
        if self._listening:
            print("[INFO] Already listening to live stream.")
            return

        self._listening = True

        def _sse_worker():
            sse_url = f"{self.base_url}/sse"
            print(f"[SSE] Connecting to live event stream at {sse_url}...")
            try:
                with requests.get(sse_url, stream=True, headers={"Accept": "text/event-stream"}) as resp:
                    resp.raise_for_status()
                    current_event = "message"

                    for line in resp.iter_lines(decode_unicode=True):
                        if not self._listening:
                            break
                        if not line:
                            continue

                        if line.startswith("event:"):
                            current_event = line.replace("event:", "").strip()
                        elif line.startswith("data:"):
                            raw_data = line.replace("data:", "").strip()

                            # Handshake detection
                            if current_event == "endpoint" and "session_id=" in raw_data:
                                self.session_id = raw_data.split("session_id=")[-1]
                                print(f"[SSE HANDSHAKE] Connected with Session ID: {self.session_id}")

                            elif current_event == "database_update":
                                parsed_event = self._parse_python_data(raw_data)
                                print(f"\n[LIVE DB UPDATE] Event: {parsed_event.get('event_type')}")
                                print(f"               Details: {parsed_event.get('details')}\n")

                            elif current_event == "ping":
                                pass
                            else:
                                print(f"[SSE {current_event.upper()}] {raw_data}")

            except Exception as e:
                if self._listening:
                    print(f"[SSE Stream Notice] Disconnected ({e})")

        self._listener_thread = threading.Thread(target=_sse_worker, daemon=True)
        self._listener_thread.start()
        time.sleep(1.0)

    def stop_listening(self) -> None:
        """Stop background event listener."""
        self._listening = False

    # =========================================================================
    # 2. Standard MCP Protocol Handshakes
    # =========================================================================

    def initialize(self) -> Dict[str, Any]:
        """Perform MCP initialize handshake."""
        result = self._send_rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "AlexaPythonClient", "version": "1.0.0"},
            },
        )
        return result

    # =========================================================================
    # 3. Tool Calls (Pure Python Methods)
    # =========================================================================

    def list_tools(self) -> List[Dict[str, Any]]:
        """Fetch list of all tools supported by the server."""
        result = self._send_rpc("tools/list")
        return result.get("tools", [])

    def create_booking(
        self,
        title: str,
        customer_name: str,
        category: str = "general",
        scheduled_time: Optional[str] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Create a booking or appointment. Writes directly to SQL database."""
        args = {
            "title": title,
            "customer_name": customer_name,
            "category": category,
            "description": description,
        }
        if scheduled_time:
            args["scheduled_time"] = scheduled_time

        result = self._send_rpc("tools/call", {"name": "alexa_create_booking", "arguments": args})
        content_text = result.get("content", [{}])[0].get("text", "{}")
        return self._parse_python_data(content_text)

    def update_booking_status(self, booking_id: str, status: str, notes: str = "") -> Dict[str, Any]:
        """Update status of a booking in Python (pending, confirmed, completed, cancelled)."""
        args = {
            "booking_id": booking_id,
            "status": status,
            "notes": notes,
        }
        result = self._send_rpc("tools/call", {"name": "alexa_update_booking_status", "arguments": args})
        content_text = result.get("content", [{}])[0].get("text", "{}")
        return self._parse_python_data(content_text)

    def query_tasks(self, status: str = "all", category: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Query tasks and bookings currently saved in the SQL database."""
        args: Dict[str, Any] = {"status": status, "limit": limit}
        if category:
            args["category"] = category

        result = self._send_rpc("tools/call", {"name": "alexa_query_tasks", "arguments": args})
        content_text = result.get("content", [{}])[0].get("text", "{}")
        return self._parse_python_data(content_text)

    def execute_automation(
        self,
        action_type: str,
        target_device_or_service: str,
        parameters: Optional[Dict[str, Any]] = None,
        notify_user: bool = True,
    ) -> Dict[str, Any]:
        """Trigger an automated smart home scene or voice workflow."""
        args = {
            "action_type": action_type,
            "target_device_or_service": target_device_or_service,
            "parameters": parameters or {},
            "notify_user": notify_user,
        }
        result = self._send_rpc("tools/call", {"name": "alexa_execute_automation", "arguments": args})
        content_text = result.get("content", [{}])[0].get("text", "{}")
        return self._parse_python_data(content_text)

    def get_system_health(self) -> Dict[str, Any]:
        """Check system uptime, database connection, and total task count."""
        result = self._send_rpc("tools/call", {"name": "alexa_get_system_health", "arguments": {}})
        content_text = result.get("content", [{}])[0].get("text", "{}")
        return self._parse_python_data(content_text)

    def read_active_bookings(self) -> Dict[str, Any]:
        """Read live MCP resource for active bookings."""
        result = self._send_rpc("resources/read", {"uri": "alexa://bookings/active"})
        contents = result.get("contents", [{}])[0].get("text", "{}")
        return self._parse_python_data(contents)


# =============================================================================
# Easy Interactive Demo (Run this script with: python client.py)
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🤖 ALEXA+ MCP 100% PURE PYTHON TESTER")
    print("=" * 70)

    client = AlexaMCPClient("http://127.0.0.1:5000")

    # 1. Start live event listener in background
    client.start_listening()

    # 2. Handshake
    print("\n--- Step 1: Connecting to MCP Server ---")
    try:
        init_res = client.initialize()
        server_name = init_res.get("serverInfo", {}).get("name")
        server_ver = init_res.get("serverInfo", {}).get("version")
        print(f" Connected to {server_name} (v{server_ver})")
    except Exception as err:
        print(f" Failed to connect to server: {err}")
        print("Please start the server first in another terminal: python app.py")
        client.stop_listening()
        exit(1)

    # 3. List tools
    print("\n--- Step 2: Available Alexa Tools ---")
    tools = client.list_tools()
    for t in tools:
        print(f"• Tool: {t['name']}")
        print(f"  Description: {t['description']}\n")

    # 4. Create a booking using Python
    print("--- Step 3: Creating a Doctor Appointment ---")
    booking = client.create_booking(
        title="Dental Checkup & Cleaning",
        customer_name="Alex Johnson",
        category="doctor",
        scheduled_time="2026-10-15T10:00:00Z",
        description="Routine 6-month checkup requested via Alexa Voice.",
    )
    print(f" Result: {booking.get('message')}")
    booking_id = booking.get("booking_id")
    print(f" Created Booking ID: {booking_id}")

    time.sleep(1)

    # 5. Execute Smart Home Automation
    print("\n--- Step 4: Triggering Smart Home Scene ---")
    automation = client.execute_automation(
        action_type="smart_home_scene",
        target_device_or_service="living_room_thermostat",
        parameters={"target_temp": 71, "eco_mode": True},
        notify_user=True,
    )
    print(f" Automation Status: {automation.get('message')}")

    time.sleep(1)

    # 6. Query Tasks from SQL Database
    print("\n--- Step 5: Querying Database Records ---")
    tasks_query = client.query_tasks(limit=5)
    print(f" Found {tasks_query.get('count')} total tasks in database:")
    for task in tasks_query.get("tasks", []):
        print(f"  - [{task['status'].upper()}] {task['title']} (ID: {task['id']})")

    # 7. Check System Health
    print("\n--- Step 6: Checking System Metrics ---")
    health = client.get_system_health()
    metrics = health.get("metrics", {})
    print(f" Server Status: {health.get('status')}")
    print(f" Total Tasks in DB: {metrics.get('total_tasks')}")
    print(f" Pending Tasks: {metrics.get('pending_tasks')}")
    print(f" Total Live Events Logged: {metrics.get('total_events_logged')}")

    print("\n All steps completed successfully in Pure Python!")
    client.stop_listening()
