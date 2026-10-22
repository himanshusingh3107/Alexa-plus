"""Test script to verify Agentic Alexa capabilities:
1. Task Completion (MCP Tools: Lights, AC, Bookings)
2. Agentic Conversation (Chit-chat, Empathy, Help)
3. Google Search Grounding (General Knowledge)
4. Combined Task + Dialogue
"""

import os
import sys

# Ensure current dir is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from dotenv import load_dotenv
load_dotenv()

from services.agent_orchestrator import AgenticOrchestrator


def main():
    print("=" * 70)
    print("🤖 ALEXA+ AGENTIC AI TEST SUITE")
    print("=" * 70)

    orchestrator = AgenticOrchestrator(user_id="test_user_001")

    test_queries = [
        # 1. Pure Conversational Agent Dialogue
        "Hey Alexa, who are you and how are you different from normal Alexa?",

        # 2. Smart Home Task Execution
        "Turn on the living room lights and set brightness to maximum",

        # 3. Grounded Knowledge Query (Google Search)
        "What is a landslide and why does it happen?",

        # 4. Multi-Slot Booking Task
        "Book a doctor appointment for Priya tomorrow at 4 PM",

        # 5. Combined Conversation + Action
        "I have a terrible headache, can you dim the lights and check my schedule?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n[{i}] 🗣️ USER: {query}")
        result = orchestrator.process_utterance(query, session_id="test-session")

        if result.get("thought"):
            print(f"    🧠 AGENT THOUGHT: {result['thought']}")
        if result.get("tool_used"):
            print(f"    ⚡ TOOL EXECUTED: {result['tool_used']}")
        else:
            print(f"    💬 AGENT CONVERSATION (No tool needed)")
        print(f"    🎙️ ALEXA SPEAKS: \"{result.get('response')}\"")

    print("\n" + "=" * 70)
    print("✅ All Agentic tests completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
