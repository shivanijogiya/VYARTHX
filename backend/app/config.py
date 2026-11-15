"""VYARTHX configuration. Reads environment variables and an optional .env file at the project root."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # backend/app/config.py -> project root
DATA_DIR = ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
UPLOAD_DIR = DATA_DIR / "uploads"
ML_DIR = ROOT / "ml"
FRONTEND_DIST = ROOT / "frontend" / "dist"


def _load_dotenv() -> None:
    for name in (".env",):
        p = ROOT / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _secret() -> str:
    env = os.environ.get("JWT_SECRET")
    if env:
        return env
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    f = DATA_DIR / ".jwt_secret"
    if f.exists():
        return f.read_text().strip()
    s = secrets.token_hex(32)
    f.write_text(s)
    return s


class Settings:
    APP_NAME = "VYARTHX"
    TAGLINE = "Segregate better. Earn responsibly. Recover more. Waste less."
    DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{(DATA_DIR / 'vyarthx.db').as_posix()}"
    JWT_SECRET = _secret()
    JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "72"))
    DEMO_MODE = _bool("DEMO_MODE", True)
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "8000"))
    # Optional LLM (reasoning narration, assistant phrasing, optional vision description).
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    LLM_MODEL = os.environ.get("VYARTHX_LLM_MODEL", "claude-sonnet-4-5")
    LLM_VISION = _bool("VYARTHX_LLM_VISION", False)
    # Free alternative: Google Gemini (key from https://aistudio.google.com/apikey)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
    LLM_PROVIDER = "anthropic" if ANTHROPIC_API_KEY else ("gemini" if GEMINI_API_KEY else "")
    OSRM_URL = os.environ.get("OSRM_URL", "")  # e.g. http://localhost:5000 (optional road routing)
    MAX_RETRIES = int(os.environ.get("AGENT_MAX_RETRIES", "2"))
    PILOT = "Tamil Nadu pilot — Greater Chennai (illustrative localities)"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.LLM_PROVIDER)

    @property
    def record_class(self) -> str:
        """Data class applied to records created while the app runs."""
        return "simulated" if self.DEMO_MODE else "pilot"


settings = Settings()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
