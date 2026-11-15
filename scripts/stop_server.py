"""Stops the VYARTHX server started by launcher.py."""
import os, signal, subprocess, sys
from pathlib import Path
PID = Path(__file__).resolve().parents[1] / "data" / "runtime" / "server.pid"
if not PID.exists():
    print("VYARTHX does not appear to be running (no PID file)."); sys.exit(0)
pid = int(PID.read_text().strip())
try:
    if os.name == "nt": subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else: os.kill(pid, signal.SIGTERM)
    print(f"Stopped VYARTHX (pid {pid}).")
except Exception as e:  # noqa: BLE001
    print("Process already stopped or could not be stopped:", e)
PID.unlink(missing_ok=True)
