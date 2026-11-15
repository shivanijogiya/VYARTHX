"""VYARTHX launcher: init DB, seed, check models, start server, wait for health, open browser.
Run by run.bat inside the project venv. Usage: python scripts/launcher.py [--no-browser]"""
import os, subprocess, sys, time, webbrowser, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
RUNTIME = ROOT / "data" / "runtime"; RUNTIME.mkdir(parents=True, exist_ok=True)
PID = RUNTIME / "server.pid"; LOG = RUNTIME / "server.log"

def step(n, msg): print(f"[{n}] {msg}", flush=True)

def port_busy(port):
    import socket
    with socket.socket() as s:
        s.settimeout(0.5); return s.connect_ex(("127.0.0.1", port)) == 0

def main():
    from app.config import settings, FRONTEND_DIST
    port = int(settings.PORT)
    base = f"http://127.0.0.1:{port}"
    step("1/6", "Initialising database and sample data (first run takes ~20 s)...")
    from app.database.db import SessionLocal, init_schema
    from app.database.seed import seed_if_empty
    init_schema()
    with SessionLocal() as db:
        print("      seeded sample data" if seed_if_empty(db) else "      database already seeded")
    step("2/6", "Checking agent workflows...")
    from app.agents import workflows  # noqa: F401
    from app.agents.runtime import WORKFLOWS
    from app.agents.graph import GRAPH_ENGINE
    print(f"      {len(WORKFLOWS)} workflows registered, orchestration engine: {GRAPH_ENGINE}")
    step("3/6", "Checking AI models...")
    from app.services import vision
    print("      vision:", vision.model_status())
    print("      forecast model trains on first request (simulated history)")
    step("4/6", "Checking frontend build...")
    if not (FRONTEND_DIST / "index.html").exists():
        print("      WARNING: frontend/dist missing. API only. Run 'npm install && npm run build' in frontend/ (needs Node 18+).")
    else:
        print("      frontend build found")
    if port_busy(port):
        try:
            urllib.request.urlopen(base + "/api/health", timeout=3); print(f"      VYARTHX already running on {base}")
            if "--no-browser" not in sys.argv: webbrowser.open(base)
            return 0
        except Exception:
            print(f"ERROR: port {port} is used by another program. Set PORT=8001 in .env and run again."); return 2
    step("5/6", f"Starting server on {base} ...")
    out = open(LOG, "ab")
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=str(ROOT / "backend"), stdout=out, stderr=out, creationflags=flags)
    PID.write_text(str(proc.pid))
    step("6/6", "Waiting for health check...")
    for _ in range(90):
        if proc.poll() is not None:
            print(f"ERROR: server exited. See {LOG}"); return 1
        try:
            urllib.request.urlopen(base + "/api/health", timeout=2); break
        except Exception:
            time.sleep(1)
    else:
        print(f"ERROR: server did not become healthy. See {LOG}"); return 1
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "health_check.py"), str(port)])
    if r.returncode: return 1
    print(f"\nVYARTHX is running at {base}\nDemo accounts are on the login page (password Vyarthx@2026). Run stop.bat to stop.\n")
    if "--no-browser" not in sys.argv: webbrowser.open(base)
    return 0

if __name__ == "__main__":
    sys.exit(main())
