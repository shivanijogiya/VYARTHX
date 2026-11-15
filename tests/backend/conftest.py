import os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
_tmp = tempfile.mkdtemp(prefix="vyarthx_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["DEMO_MODE"] = "true"
os.environ.pop("ANTHROPIC_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def H(client):
    def login(e):
        r = client.post("/api/auth/login", json={"email": e, "password": "Vyarthx@2026"})
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["token"]}
    return {k: login(f"{k}@vyarthx.demo") for k in ("citizen", "citizen2", "worker", "facility", "recycler", "municipal", "organiser")}


@pytest.fixture()
def img():
    from app.services.demo_story import synthetic_image
    import random
    return lambda: synthetic_image(random.randint(1, 10**6))
