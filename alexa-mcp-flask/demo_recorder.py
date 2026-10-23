"""Alexa+ Automated Live Demo & Slide Presentation Controller.

Run this script in terminal while recording your hackathon presentation video.
It gives you complete control over:
1. Auto-switching all 6 pitch deck slides at http://localhost:5000/presentation
2. Interactive manual slide switching (type 1-6 or next/prev in terminal)
3. Running live voice commands against the Alexa+ MCP server (audio + telemetry)
4. Full 3-minute seamless presentation + live demo recording flow!
"""

import sys
import time
import requests

BASE_URL = "http://127.0.0.1:5000"

SLIDES = [
    {
        "index": 0,
        "title": "Part 1: The Pitch & Hook (Vision)",
        "duration": 25,
        "script": (
            "Hello judges! We are excited to present Alexa+ — our submission for the Alexa+ Platform track. "
            "Traditional voice assistants are limited by rigid intent matching and complete amnesia after every session. "
            "Alexa+ solves this by fusing modern LLM intelligence, the Model Context Protocol, and a persistent memory engine "
            "to deliver an assistant that truly understands, remembers, and acts."
        ),
    },
    {
        "index": 1,
        "title": "Part 2: The Core Problem & Our Shift",
        "duration": 30,
        "script": (
            "If you say 'book my usual doctor tomorrow morning' to traditional Alexa, it fails because it doesn't "
            "remember who your doctor is or what morning means to you. Alexa+ bridges this gap. Our Contextual Memory Engine "
            "recalls past interactions, while Gemini 3.8 Flash extracts slots from natural speech and dynamically routes "
            "actions to backend MCP tools."
        ),
    },
    {
        "index": 2,
        "title": "Part 3: Multi-Protocol System Architecture",
        "duration": 35,
        "script": (
            "Here is how our architecture works: Voice requests enter AWS Lambda through the Alexa Skills Kit. "
            "Before routing, our system fetches the user's profile and dialogue history from our hybrid SQLite and Turso database. "
            "Gemini 3.8 Flash receives this context along with all registered MCP tool schemas. The model returns a structured "
            "Pydantic decision, invoking the right MCP tool over JSON-RPC and generating conversational voice speech."
        ),
    },
    {
        "index": 3,
        "title": "Part 4: Live Web Demonstration & MCP Tools",
        "duration": 50,
        "script": (
            "Let's see Alexa+ in action on our live dashboard at localhost:5000. I'll click the microphone: "
            "'Book a doctor consultation for Kanak tomorrow at 10 AM'. In milliseconds, Gemini parses the intent, "
            "invokes alexa_create_booking via MCP, saves it into our SQL database, and Alexa speaks the confirmation aloud. "
            "Notice the live SSE telemetry terminal on the right logging every event, and the database table immediately "
            "showing the new pending booking."
        ),
    },
    {
        "index": 4,
        "title": "Part 5: AWS SAM & Production-Grade Readiness",
        "duration": 25,
        "script": (
            "Alexa+ isn't just a prototype — it's production engineered. We have an AWS SAM template ready for serverless "
            "deployment, a hybrid Turso Cloud synchronization layer, and an automated Python client test suite. "
            "The skill handles edge cases gracefully, falling back seamlessly if connectivity is interrupted."
        ),
    },
    {
        "index": 5,
        "title": "Part 6: Conclusion, Roadmap & Closing",
        "duration": 15,
        "script": (
            "Alexa+ represents the shift from rigid commands to autonomous voice intelligence. Our code, interaction model, "
            "and SAM templates are open on GitHub. Thank you judges, and we look forward to bringing Alexa+ to the Amazon Alexa ecosystem!"
        ),
    },
]

DEMO_VOICE_COMMANDS = [
    {
        "title": "Step 1: Check System Health via MCP Tool",
        "command": "Check system health report",
        "pause": 4,
    },
    {
        "title": "Step 2: Natural Speech Appointment Booking",
        "command": "Book a doctor consultation for Kanak tomorrow at 10 AM",
        "pause": 5,
    },
    {
        "title": "Step 3: Smart Home Automation Execution (Lights)",
        "command": "Turn on living room lights",
        "pause": 4,
    },
    {
        "title": "Step 4: Smart Home Automation Execution (Water Motor)",
        "command": "Turn on water motor",
        "pause": 4,
    },
    {
        "title": "Step 5: Query Database Tasks via MCP",
        "command": "What tasks and bookings are on my schedule?",
        "pause": 5,
    },
    {
        "title": "Step 6: Agentic Alexa & Team Invictus Attribution",
        "command": "Tumhe kisne banaya hai aur tum kya ho?",
        "pause": 5,
    },
]


def check_server() -> bool:
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def switch_remote_slide(slide_index: int) -> bool:
    try:
        r = requests.post(
            f"{BASE_URL}/api/presentation/slide",
            json={"slide": slide_index},
            timeout=3,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"   [Error switching slide: {e}]")
        return False


def print_banner():
    print("\n" + "=" * 74)
    print("🎬 ALEXA+ LIVE VIDEO DEMO & SLIDE CONTROLLER")
    print("=" * 74)
    print(f"👉 Backend Server:        {BASE_URL}")
    print(f"👉 Presentation Deck:    {BASE_URL}/presentation")
    print(f"👉 Web Console App:      {BASE_URL}/")
    print("=" * 74)


def run_slide_sequence(auto_wait=True):
    print("\n" + "-" * 74)
    print("📽️  PRESENTATION SLIDES CONTROLLER (ALL 6 SLIDES)")
    print("-" * 74)
    print("Make sure your browser has http://localhost:5000/presentation OPEN.")
    print("Press [ENTER] to advance immediately, or let the timer run.")
    input("\n👉 Press [ENTER] to begin Slide 1...")

    for i, slide in enumerate(SLIDES):
        idx = slide["index"]
        success = switch_remote_slide(idx)
        status_txt = "✅ Switched" if success else "⚠️ Broadcast Failed"

        print("\n" + "=" * 74)
        print(f"🎞️  [SLIDE {idx + 1}/6] {slide['title']} | {status_txt}")
        print(f"⏱️  Target Duration: {slide['duration']} Seconds")
        print("-" * 74)
        print("🎙️  Spoken Script (Read Aloud For Video):")
        print(f'"{slide["script"]}"')
        print("-" * 74)

        if auto_wait:
            print(f"⏳ Reading timer ({slide['duration']}s)... Press [ENTER] when done to skip countdown: ", end="", flush=True)
            # Give presenter convenient time or manual skip
            start_t = time.time()
            try:
                # Wait for duration or Enter
                import msvcrt
                aborted = False
                while time.time() - start_t < slide["duration"]:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key in (b"\r", b"\n", b" "):
                            aborted = True
                            break
                    time.sleep(0.1)
                if aborted:
                    print(" [Next slide selected!]")
                else:
                    print(f" [Time's up ({slide['duration']}s)!]")
            except Exception:
                # Fallback on standard platforms
                time.sleep(slide["duration"])
        else:
            input("\n👉 Press [ENTER] to switch to next slide...")

    print("\n" + "=" * 74)
    print("🎉 ALL 6 SLIDES PRESENTED SUCCESSFULLY!")
    print("=" * 74)


def run_voice_simulation():
    print("\n" + "-" * 74)
    print("⚡ LIVE VOICE & MCP TOOL SIMULATION")
    print("-" * 74)
    print("Make sure http://localhost:5000 is open with sound ON to hear Alexa TTS.")
    input("\n👉 Press [ENTER] to start voice sequence...")

    for i, step in enumerate(DEMO_VOICE_COMMANDS, 1):
        print(f"\n▶ [{i}/{len(DEMO_VOICE_COMMANDS)}] {step['title']}")
        print(f"   🗣️ Utterance: \"{step['command']}\"")
        print("   ⚡ Sending to Alexa+ backend...")

        try:
            t0 = time.time()
            resp = requests.post(
                f"{BASE_URL}/api/dashboard/simulate",
                json={"utterance": step["command"]},
                timeout=12,
            )
            elapsed = round((time.time() - t0) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                print(f"   🔧 Tool Executed: {data.get('tool_used') or 'None'}")
                print(f"   💬 Alexa Reply:   \"{data.get('response')}\"")
                print(f"   ⏱️ Response Time: {elapsed}ms")
            else:
                print(f"   ⚠️ Status {resp.status_code}: {resp.text}")
        except Exception as err:
            print(f"   ❌ Error: {err}")

        print(f"   [Pausing {step['pause']}s for voice playback / recording...]")
        time.sleep(step["pause"])

    print("\n" + "=" * 74)
    print("🎉 VOICE & MCP DEMO COMPLETED!")
    print("Check your web console table and live SSE terminal.")
    print("=" * 74)


def run_full_3min_pitch():
    print("\n" + "=" * 74)
    print("🚀 FULL 3-MINUTE HACKATHON RECORDING SEQUENCE")
    print("=" * 74)
    print("Flow:")
    print("  • Slide 1: Hook & Vision (0:00 - 0:25)")
    print("  • Slide 2: The Shift (0:25 - 0:55)")
    print("  • Slide 3: Architecture (0:55 - 1:30)")
    print("  • Slide 4: Live Demo (1:30 - 2:20) + Automated Voice Commands!")
    print("  • Slide 5: Cloud & AWS SAM (2:20 - 2:45)")
    print("  • Slide 6: Roadmap & Closing (2:45 - 3:00)")
    print("=" * 74)
    input("\n👉 Start your screen recorder, then press [ENTER] to begin...")

    # Slides 1, 2, 3
    for s_idx in [0, 1, 2]:
        slide = SLIDES[s_idx]
        switch_remote_slide(s_idx)
        print(f"\n🎞️  [SLIDE {s_idx + 1}/6] {slide['title']}")
        print(f"⏱️  Duration: {slide['duration']}s | Spoken Script:\n\"{slide['script']}\"")
        print("\nPress [ENTER] to advance when you finish speaking...", end="", flush=True)
        # Give presenter time or keypress
        start_t = time.time()
        import msvcrt
        while time.time() - start_t < slide["duration"]:
            if msvcrt.kbhit() and msvcrt.getch() in (b"\r", b"\n", b" "):
                break
            time.sleep(0.1)

    # Slide 4: Live Demo
    switch_remote_slide(3)
    slide4 = SLIDES[3]
    print(f"\n🎞️  [SLIDE 4/6] {slide4['title']}")
    print(f"Script: \"{slide4['script']}\"\n")
    print("Switch screen to http://localhost:5000 now! Running live commands in 4s...")
    time.sleep(4)

    # Run top voice commands
    for step in DEMO_VOICE_COMMANDS[:4]:
        print(f"\n⚡ Simulating: \"{step['command']}\"")
        try:
            requests.post(f"{BASE_URL}/api/dashboard/simulate", json={"utterance": step["command"]}, timeout=10)
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(step["pause"])

    # Slide 5 and 6
    for s_idx in [4, 5]:
        slide = SLIDES[s_idx]
        switch_remote_slide(s_idx)
        print(f"\n🎞️  [SLIDE {s_idx + 1}/6] {slide['title']}")
        print(f"⏱️  Duration: {slide['duration']}s | Spoken Script:\n\"{slide['script']}\"")
        start_t = time.time()
        import msvcrt
        while time.time() - start_t < slide["duration"]:
            if msvcrt.kbhit() and msvcrt.getch() in (b"\r", b"\n", b" "):
                break
            time.sleep(0.1)

    print("\n" + "=" * 74)
    print("🎉 FULL 3-MINUTE HACKATHON PITCH RECORDING COMPLETED!")
    print("=" * 74)


def run_interactive_controller():
    current_idx = 0
    switch_remote_slide(current_idx)

    print("\n" + "-" * 74)
    print("🎮 INTERACTIVE MANUAL SLIDE CONTROLLER")
    print("-" * 74)
    print("Commands:")
    print("  [1] to [6] : Jump immediately to Slide 1-6")
    print("  'n' / 'next': Next slide")
    print("  'p' / 'prev': Previous slide")
    print("  'q' / 'exit': Back to main menu")
    print("-" * 74)

    while True:
        slide = SLIDES[current_idx]
        print(f"\n📍 CURRENT: [Slide {current_idx + 1}/6] {slide['title']}")
        print(f'   Script: "{slide["script"][:120]}..."')
        cmd = input("Slide Command (1-6, n, p, q) > ").strip().lower()

        if cmd in ("q", "exit"):
            break
        elif cmd in ("n", "next", ""):
            current_idx = min(5, current_idx + 1)
        elif cmd in ("p", "prev"):
            current_idx = max(0, current_idx - 1)
        elif cmd in [str(i) for i in range(1, 7)]:
            current_idx = int(cmd) - 1
        else:
            print("Invalid command. Use 1-6, n, p, or q.")
            continue

        switch_remote_slide(current_idx)
        print(f"✅ Switched browser to Slide {current_idx + 1}!")


def reset_demo_state():
    print("\n🔄 Resetting demo tasks and telemetry in database...")
    try:
        r = requests.post(f"{BASE_URL}/api/dashboard/reset", timeout=5)
        if r.status_code == 200:
            print("✅ Reset successful! Database & telemetry cleared.")
        else:
            print(f"⚠️ Server returned status {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ Failed to reset: {e}")


def main_menu():
    print_banner()

    print("\nChecking Alexa+ server status at http://127.0.0.1:5000...")
    if not check_server():
        print("❌ Cannot reach server! Please make sure 'py app.py' is running in another terminal.")
        print("Start it with: cd alexa-mcp-flask && py app.py\n")
    else:
        print("✅ Server is ONLINE and ready!\n")

    while True:
        print("\nChoose an option:")
        print("  [1] 📽️  Auto-Switch All 6 Presentation Slides (with Teleprompter)")
        print("  [2] ⚡  Run Live Voice & MCP Simulator Demo")
        print("  [3] 🚀  Full 3-Minute Hackathon Recording Run (Slides + Live Demo)")
        print("  [4] 🎮  Interactive Manual Slide Controller (1-6, Next, Prev)")
        print("  [5] 🔄  Reset Demo State (Clear Tasks & Telemetry)")
        print("  [0] ❌  Exit")

        choice = input("\nEnter choice [1-5, 0]: ").strip()

        if choice == "1":
            run_slide_sequence(auto_wait=True)
        elif choice == "2":
            run_voice_simulation()
        elif choice == "3":
            run_full_3min_pitch()
        elif choice == "4":
            run_interactive_controller()
        elif choice == "5":
            reset_demo_state()
        elif choice == "0":
            print("\n👋 Exiting. Good luck with the Hackathon!\n")
            sys.exit(0)
        else:
            print("Invalid selection, please try again.")


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
