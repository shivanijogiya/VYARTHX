# Troubleshooting

| Symptom | Fix |
|---|---|
| "Python 3.10 or newer was not found" | Install from python.org, tick *Add python.exe to PATH*, rerun `run.bat`. |
| pip install fails (offline / proxy) | Connect to the internet for the first run; or `.venv\Scripts\pip install -r requirements.lock`. |
| onnxruntime / ortools wheel unavailable | Use 64-bit Python 3.10–3.13. The app still runs without them (keyword classifier, greedy router) but warns in Data & Honesty. |
| Port 8000 busy | Put `PORT=8001` in `.env`, rerun. |
| Blank page / "frontend build not found" | `frontend\dist` is bundled. If missing: install Node 18+, `cd frontend && npm install && npm run build`. |
| Map tiles are grey | Needs internet for OpenStreetMap tiles; markers still work. |
| Login says session expired after reset | Sign in again. |
| Reset everything | Stop, delete `data\vyarthx.db*`, run `run.bat` (or Municipal → Guided Demo → Reset sample data). |
| Logs | `data\runtime\server.log` |
