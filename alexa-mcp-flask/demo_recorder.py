"""Automated Live Demo Script for Presentation Video Recording.

Run this script in terminal while recording your screen.
It simulates real voice commands against the running Alexa+ server,
triggering live audio playback, MCP tool executions, and real-time SSE telemetry!
"""

import time
import requests

BASE_URL = "http://127.0.0.1:5000"

DEMO_SEQUENCE = [
    {
        "title": "Step 1: Check System Health via MCP Tool",
        "command": "Check system health report",
        "pause": 4,
    },
    {
        "title": "Step 2: Natural Speech Appointment Booking",
        "command": "Book a dentist consultation for Sarah tomorrow at 10 AM",
        "pause": 6,
    },
    {
        "title": "Step 3: Smart Home Automation Execution",
        "command": "Turn on the living room air conditioner to 70 degrees",
        "pause": 6,
    },
    {
        "title": "Step 4: Query Database Tasks via MCP",
        "command": "What tasks and bookings are on my schedule?",
        "pause": 5,
    },
]


def print_banner():
    print("=" * 70)
    print("🎬 ALEXA+ LIVE VIDEO DEMO AUTOMATOR")
    print("=" * 70)
    print("Instructions for Recording:")
    print("1. Open http://localhost:5000 in your browser (Reddish-Black Dashboard).")
    print("2. Ensure browser volume is ON so Alexa's voice (TTS) is audible.")
    print("3. Start your screen recorder (OBS, Loom, or Win + G).")
    print("4. Press ENTER below to start the automated sequence!")
    print("=" * 70)


def run_demo():
    print_banner()
    input("\n👉 Press [ENTER] when your screen recorder is running...")

    print("\n[INFO] Checking if Alexa+ server is live...")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        if r.status_code != 200:
            print("[ERROR] Server returned non-200 status. Make sure 'python app.py' is running!")
            return
    except Exception as e:
        print(f"[ERROR] Cannot reach server at {BASE_URL}: {e}")
        print("Please start the server first in another terminal: python app.py")
        return

    print(" Server is ONLINE! Starting demo sequence in 3 seconds...\n")
    time.sleep(3)

    for i, step in enumerate(DEMO_SEQUENCE, 1):
        print(f"\n▶ [{i}/{len(DEMO_SEQUENCE)}] {step['title']}")
        print(f"   Utterance: \"{step['command']}\"")
        print("   Sending to backend...")

        try:
            start_t = time.time()
            resp = requests.post(
                f"{BASE_URL}/api/dashboard/simulate",
                json={"utterance": step["command"]},
                timeout=10,
            )
            elapsed = round((time.time() - start_t) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                print(f"   ⚡ MCP Tool: {data.get('tool_used') or 'None'}")
                print(f"   🗣️ Alexa Spoke: \"{data.get('response')}\"")
                print(f"   ⏱️ Response Time: {elapsed}ms")
            else:
                print(f"   ⚠️ Status {resp.status_code}: {resp.text}")

        except Exception as err:
            print(f"   ❌ Error: {err}")

        print(f"   [Pausing {step['pause']}s for video recording / voice playback...]")
        time.sleep(step["pause"])

    print("\n" + "=" * 70)
    print("🎉 DEMO SEQUENCE COMPLETED SUCCESSFULLY!")
    print("Check your dashboard table and live SSE terminal to show the final state.")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
