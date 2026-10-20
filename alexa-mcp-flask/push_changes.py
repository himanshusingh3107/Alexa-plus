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

print("=== Git Status ===")
run_git(["status"])

print("\n=== Adding modified files ===")
run_git(["add", "alexa-mcp-flask/templates/index.html", "alexa-mcp-flask/app.py"])

print("\n=== Committing ===")
run_git(["commit", "-m", "feat: add interactive web dashboard with mic speech-to-text and Alexa voice TTS"])

print("\n=== Pushing to origin main ===")
code = run_git(["push", "origin", "main"])

if code == 0:
    print("\nSUCCESS: Pushed to GitHub successfully!")
else:
    print("\nFAILED to push. Check output above.")
