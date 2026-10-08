"""Connect this project to your new Git repository using Python only.

Run this script:
    python git_setup.py
"""

import sys
import subprocess


def run_cmd(command: list[str]) -> bool:
    print(f"\n[RUNNING] {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result.returncode == 0


def main():
    print("=" * 60)
    print("📦 PYTHON GIT REPO CONNECTOR")
    print("=" * 60)

    repo_url = input("\nEnter your Git Repository URL (e.g. https://github.com/username/alexa-plus.git):\n> ").strip()

    if not repo_url:
        print("Error: No URL entered. Aborting.")
        sys.exit(1)

    print(f"\nConnecting to: {repo_url} ...")

    # 1. Switch to main branch
    run_cmd(["git", "branch", "-M", "main"])

    # 2. Check if origin already exists, otherwise add it
    res = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
    if res.returncode == 0:
        print("Remote 'origin' already exists. Updating to new URL...")
        run_cmd(["git", "remote", "set-url", "origin", repo_url])
    else:
        run_cmd(["git", "remote", "add", "origin", repo_url])

    # 3. Stage all files
    print("\nAdding files to git...")
    run_cmd(["git", "add", "."])

    # 4. Commit
    print("\nCommitting codebase...")
    run_cmd(["git", "commit", "-m", "feat: initial commit for Alexa+ MCP server"])

    # 5. Push
    print("\nPushing to remote repository...")
    success = run_cmd(["git", "push", "-u", "origin", "main"])

    if success:
        print("\n🎉 SUCCESS! Your code is now connected and uploaded to your Git repository!")
    else:
        print("\nNote: If the remote repo already had a README or license, run:")
        print("git pull origin main --allow-unrelated-histories")
        print("then run: python git_setup.py again.")


if __name__ == "__main__":
    main()

