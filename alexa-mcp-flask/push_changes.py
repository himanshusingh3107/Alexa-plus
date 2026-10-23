import os
import subprocess

repo_dir = r"C:\Users\vs623\OneDrive\Desktop\PROJECTS\Alexa+"

def run_git(args):
    print(f"Running: git {' '.join(args)}")
    res = subprocess.run(["git"] + args, cwd=repo_dir, capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr)
    return res.returncode

print("=== Git Status Before Add ===")
run_git(["status"])

print("\n=== Adding modified and new demo files ===")
run_git(["add",
    "alexa-mcp-flask/README.md",
    "alexa-mcp-flask/.env.example",
    "alexa-mcp-flask/demo_recorder.py",
    "alexa-mcp-flask/templates/presentation.html",
    "alexa-mcp-flask/push_changes.py",
])

# Ensure secrets and databases are never staged
run_git(["reset", "HEAD", "alexa-mcp-flask/.env"])
run_git(["reset", "HEAD", ".env"])
run_git(["reset", "HEAD", "alexa-mcp-flask/alexa_mcp.db"])
run_git(["reset", "HEAD", "alexa_mcp.db"])

print("\n=== Staged Files ===")
run_git(["status", "--short"])

print("\n=== Committing ===")
run_git(["commit", "-m", "docs & demo: update README, .env.example, add automated demo recorder and 3-minute hackathon pitch deck"])

print("\n=== Pushing to origin main ===")
code = run_git(["push", "origin", "main"])

if code == 0:
    print("\n🎉 SUCCESS: Git commit and push completed successfully!")
else:
    print("\nFAILED to push. Check output above.")
