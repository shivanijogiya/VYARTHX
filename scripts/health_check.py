"""Checks a running VYARTHX server. Usage: python scripts/health_check.py [port]  (exit 0 = healthy)"""
import json, sys, urllib.request

port = sys.argv[1] if len(sys.argv) > 1 else "8000"
base = f"http://127.0.0.1:{port}"
def get(p):
    with urllib.request.urlopen(base + p, timeout=8) as r:
        return r.status, r.read()
try:
    s, b = get("/api/health"); h = json.loads(b)
    assert s == 200 and h["status"] == "ok", h
    s, b = get("/api/meta"); assert s == 200 and json.loads(b)["wards"], "no wards - database not seeded"
    s, b = get("/"); assert s == 200 and b"<div id=\"root\">" in b or b"VYARTHX" in b, "frontend not served"
    print("HEALTHY: API, database, seed data and frontend are responding on", base)
except Exception as e:  # noqa: BLE001
    print("UNHEALTHY:", e); sys.exit(1)
