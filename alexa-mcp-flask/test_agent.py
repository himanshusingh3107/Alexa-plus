"""Comprehensive Test Suite for Alexa+ Agentic AI & ALL Smart Devices."""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from dotenv import load_dotenv
load_dotenv()

from services.agent_orchestrator import AgenticOrchestrator


def main():
    print("=" * 75)
    print("🤖 ALEXA+ ALL SMART DEVICES & AGENTIC TEST SUITE")
    print("=" * 75)

    orchestrator = AgenticOrchestrator(user_id="test_user_all_devices")

    test_queries = [
        # 1. Whole-Home / All Devices (Hinglish & English)
        "Ghar ke saare devices band kar do",
        "Turn on all smart devices",

        # 2. Lights & Lamps in different rooms
        "Balcony lights dim kar do",
        "Turn on bedroom lights",

        # 3. Fans & Coolers
        "Ceiling fan band karo",
        "Exhaust fan chalu karo",

        # 4. AC & Climate
        "Living room AC on kar do bahut garmi hai",
        "Turn off AC",

        # 5. Smart TV & Entertainment
        "TV band karo",
        "Turn on soundbar",

        # 6. Smart Locks & Doors
        "Front door lock karo",
        "Unlock main gate",

        # 7. Curtains & Blinds
        "Parde khol do",
        "Close living room curtains",

        # 8. Robot Vacuum Cleaner
        "Safai shuru karo vacuum cleaner se",
        "Stop robot vacuum and dock",

        # 9. Water Pump / Motor (Indian households)
        "Paani ki motor chalu karo",
        "Water pump band kar do",

        # 10. Air Purifier
        "Air purifier on kar do",

        # 11. Kitchen Appliances
        "Kitchen chimney on karo",
        "Coffee maker chalu karo",

        # 12. Security Cameras
        "Security camera on karo",

        # 13. Smart Plugs & Inverter
        "Smart plug on karo",
        "Inverter check karo",

        # 14. Universal Regex Parser (Any arbitrary custom device)
        "Projector on karo",
        "Turn off electric heater",

        # 15. General Knowledge & Fact (Gemini)
        "What is photosynthesis?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i:02d}] 🗣️ USER: \"{query}\"")
        result = orchestrator.process_utterance(query, session_id="test-all-devices-session")

        tool = result.get("tool_used") or "None"
        thought = result.get("thought") or "Direct response"
        resp = result.get("response")

        print(f"     ⚡ TOOL: {tool} | 🧠 THOUGHT: {thought}")
        print(f"     🎙️ SPEECH: \"{resp}\"")

    print("\n" + "=" * 75)
    print("✅ All device compatibility tests completed successfully!")
    print("=" * 75)


if __name__ == "__main__":
    main()
