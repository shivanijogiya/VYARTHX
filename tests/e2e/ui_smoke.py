"""UI smoke test: signs in as every demo role, opens every reachable page, and reports
JS errors, failed API calls and empty pages. Needs the server running and Chrome/Chromium
(set CHROME_PATH if it is not at a standard location).  Usage: python tests/e2e/ui_smoke.py [base_url]"""
import os, shutil, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PW = "Vyarthx@2026"
ROLES = {
    "citizen@vyarthx.demo": ["/", "/doctor", "/pickups", "/wallet", "/rewards", "/passports", "/community", "/hotspots", "/marketplace", "/reuse", "/compost", "/special", "/events", "/reports", "/agents", "/demo", "/sources"],
    "worker@vyarthx.demo": ["/worker", "/doctor", "/hotspots", "/special", "/agents"],
    "facility@vyarthx.demo": ["/facility", "/passports", "/marketplace", "/events", "/compost"],
    "recycler@vyarthx.demo": ["/facility", "/marketplace"],
    "organiser@vyarthx.demo": ["/", "/events"],
    "municipal@vyarthx.demo": ["/command", "/logistics", "/landfill", "/twin", "/reports", "/agents", "/passports", "/community", "/hotspots", "/marketplace", "/events", "/demo", "/sources"],
}
chrome = os.environ.get("CHROME_PATH") or shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
problems, visited = [], 0
shots = os.environ.get("SHOT_DIR")
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=chrome, headless=True, args=["--no-sandbox"])
    for email, paths in ROLES.items():
        ctx = b.new_context(viewport={"width": 1366, "height": 850})
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        page.on("console", lambda m: m.type == "error" and "tile.openstreetmap" not in m.text and "ERR_" not in m.text and errs.append(f"console: {m.text[:200]}"))
        page.on("response", lambda r: r.url.startswith(BASE + "/api") and r.status >= 400 and errs.append(f"HTTP {r.status} {r.url.replace(BASE, '')}"))
        page.goto(BASE + "/login"); page.wait_for_selector("text=Sign in")
        page.fill("#e", email); page.fill("#p", PW); page.click("button:has-text('Sign in') >> nth=-1")
        page.wait_for_selector("header", timeout=15000)
        for path in paths:
            errs.clear()
            page.goto(BASE + path); page.wait_for_selector("main h1", timeout=15000)
            page.wait_for_load_state("networkidle"); page.wait_for_timeout(500)
            txt = page.inner_text("main")
            visited += 1
            if "Couldn’t load this" in txt: errs.append("page shows load error: " + txt[txt.index("Couldn’t load"):][:160].replace("\n", " "))
            if len(txt) < 80: errs.append("page nearly empty")
            if errs: problems.append((email, path, list(errs)))
            if shots: page.screenshot(path=f"{shots}/{email.split('@')[0]}{path.replace('/', '_') or '_home'}.png")
        ctx.close()
    b.close()
print(f"visited {visited} pages")
for e, pth, er in problems: print("PROBLEM", e, pth, er)
print("OK - no problems" if not problems else f"{len(problems)} pages with problems")
sys.exit(1 if problems else 0)
