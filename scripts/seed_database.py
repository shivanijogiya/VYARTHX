"""Create tables and seed sample data. Usage: python scripts/seed_database.py [--reset]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database.db import SessionLocal, init_schema  # noqa: E402
from app.database.seed import reset_schema, seed_all, seed_activity, seed_if_empty  # noqa: E402

if __name__ == "__main__":
    init_schema()
    with SessionLocal() as db:
        if "--reset" in sys.argv:
            reset_schema(db)
            print("seeded:", seed_all(db))
            seed_activity(db)
        else:
            print("seeded now" if seed_if_empty(db) else "database already seeded (use --reset to rebuild)")
