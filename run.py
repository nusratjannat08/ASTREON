"""
ASTREON Application Launcher
Starts the local Flask mission intelligence server and automatically opens the browser.
"""

import sys
import os
import time
import webbrowser
import threading
from pathlib import Path

# Ensure working directory is the project directory
os.chdir(Path(__file__).resolve().parent)

try:
    from app import app, init_db
except ModuleNotFoundError as e:
    if "flask" in str(e).lower():
        venv_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists() and sys.executable.lower() != str(venv_python).lower():
            import subprocess
            print("[ASTREON] Automatically using local virtual environment (.venv)...")
            sys.exit(subprocess.call([str(venv_python)] + sys.argv))

        print("=" * 65)
        print(" [ASTREON ERROR] Required dependency 'Flask' is not installed.")
        print(" Please install it by running:")
        print("     pip install -r requirements.txt")
        print("=" * 65)
        sys.exit(1)
    raise

def open_browser():
    time.sleep(1.2)
    url = "http://127.0.0.1:5000"
    print(f"\n[ASTREON] Opening application in browser: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    init_db()
    print("=" * 65)
    print(" ASTREON - Mars Mission Site Intelligence Platform")
    print(" Launching Mission Control Software...")
    print(" Local Web Interface: http://127.0.0.1:5000")
    print(" Press Ctrl+C in this terminal to shut down.")
    print("=" * 65)

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
