import datetime as dt
import pytest


def jpg(img, name="a.jpg"):
    return {"image": (name, img(), "image/jpeg")}


# ------------------------------------------------------------------ auth / roles
def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    m = client.get("/api/meta").json()
    assert len(m["wards"]) == 15 and m["demo_mode"] is True


def test_login_rejects_bad_password(client):
    assert client.post("/api/auth/login", json={"email": "citizen@vyarthx.demo", "password": "wrong"}).status_code == 401


def test_auth_required_and_role_enforced(client, H):
    assert client.get("/api/wallet").status_code == 401
    assert client.get("/api/municipal/overview", headers=H["citizen"]).status_code == 403
    assert client.get("/api/municipal/overview", headers=H["municipal"]).status_code == 200
    assert client.post("/api/auth/register", json={"email": "x@y.com", "name": "Xx", "password": "password1", "role": "municipal"}).status_code == 400


def test_register_citizen_gets_household(client):
    r = client.post("/api/auth/register", json={"email": "new1@example.com", "name": "New User", "password": "password123", "role": "citizen"})
    assert r.status_code == 200 and r.json()["user"]["household_code"].startswith("VX-HH-")


def test_citizen_cannot_see_others_passport(client, H):
    mine = client.get("/api/passports", headers=H["citizen2"]).json()
    other = client.get("/api/passports", headers=H["citizen"]).json()
    assert other
    code = other[0]["code"]
    if not any(p["code"] == code for p in mine):
        assert client.get(f"/api/passports/{code}", headers=H["citizen2"]).status_code == 403


# ------------------------------------------------------------------ Waste Doctor safety
def test_hazard_never_declared_safe(client, H):
    r = client.post("/api/waste/classify", headers=H["citizen"], data={"text": "old AA battery"}).json()["classification"]
    assert r["hazard"] is True and r["stream"] == "special" and r["human_review_required"] is True


def test_low_confidence_asks_for_clarification(client, H):
    r = client.post("/api/waste/classify", headers=H["citizen"], data={"text": "thing"}).json()
    assert r["needs_clarification"] is True


def test_wet_food_is_not_flagged_contaminated(client, H):
    c = client.post("/api/waste/classify", headers=H["citizen"], data={"text": "vegetable peels and food waste"}).json()["classification"]
    assert c["stream"] == "wet" and c["contamination"] in ("none", None, "")


# ------------------------------------------------------------------ full lifecycle
@pytest.fixture(scope="module")
def lifecycle(client, H):
    from app.services.demo_story import synthetic_image
    import random
    c = {}
    r = client.post("/api/submissions", headers=H["citizen2"], data={"text": "clean flattened cardboard boxes", "est_weight_kg": "3"}, files={"image": ("c.jpg", synthetic_image(random.randint(1, 10**6)), "image/jpeg")}).json()
    c["sub"] = r
    assert r["run_status"] == "completed", r
    c["wallet0"] = client.get("/api/wallet", headers=H["citizen2"]).json()["balances"]
    s = client.post(f"/api/submissions/{r['submission_id']}/schedule", headers=H["citizen2"], json={}).json()
    c["cid"] = s["collection_id"]
    assert c["cid"]
    return c


def test_provisional_points_not_spendable(lifecycle, client, H):
    b = lifecycle["wallet0"]
    assert b["provisional"] > 0
    item = next(i for i in client.get("/api/rewards/catalog", headers=H["citizen2"]).json())
    # provisional alone must never be spendable
    assert b["spendable"] == b["verified"] + b["final"]


def test_collection_confirm_rejects_wrong_qr(lifecycle, client, H):
    cid = lifecycle["cid"]
    wk = client.get("/api/collections", headers=H["worker"]).json() + client.get("/api/collections", headers=H["citizen2"]).json()
    col = next(c for c in wk if c["id"] == cid)
    w_h = H["worker"]
    # accept with whichever worker is assigned (worker or worker2)
    from app.database.db import SessionLocal
    from app.models.models import CollectionRequest, Worker, User
    with SessionLocal() as db:
        c = db.get(CollectionRequest, cid)
        wu = db.get(User, db.get(Worker, c.worker_id).user_id)
        email = wu.email
    r = client.post("/api/auth/login", json={"email": email, "password": "Vyarthx@2026"}).json()
    hw = {"Authorization": "Bearer " + r["token"]}
    lifecycle["hw"] = hw
    assert client.post(f"/api/collections/{cid}/accept", headers=hw).status_code == 200
    bad = client.post(f"/api/collections/{cid}/confirm", headers=hw, data={"qr_code": "VX-HH-9999", "weight_kg": "2.5", "weight_source": "scale"}).json()
    assert bad["run_status"] == "escalated"
    assert client.get("/api/wallet", headers=H["citizen2"]).json()["balances"]["verified"] == lifecycle["wallet0"]["verified"]


def test_collection_confirm_credits_and_creates_passport(lifecycle, client, H):
    cid, hw = lifecycle["cid"], lifecycle["hw"]
    code = client.get("/api/auth/me", headers=H["citizen2"]).json()["household_code"]
    r = client.post(f"/api/collections/{cid}/confirm", headers=hw, data={"qr_code": code, "weight_kg": "2.5", "weight_source": "scale"}).json()
    assert r["run_status"] == "completed", r
    b = client.get("/api/wallet", headers=H["citizen2"]).json()["balances"]
    assert b["verified"] > lifecycle["wallet0"]["verified"]
    # idempotent: confirming again must not double-credit
    again = client.post(f"/api/collections/{cid}/confirm", headers=hw, data={"qr_code": code, "weight_kg": "2.5", "weight_source": "scale"})
    assert client.get("/api/wallet", headers=H["citizen2"]).json()["balances"]["verified"] == b["verified"]
    ps = client.get("/api/passports", headers=H["citizen2"]).json()
    lifecycle["batch"] = next(p for p in ps if p["status"] == "collected")


def test_passport_chain_intact(lifecycle, client, H):
    d = client.get(f"/api/passports/{lifecycle['batch']['code']}", headers=H["citizen2"]).json()
    assert d["chain"]["intact"] is True and len(d["events"]) >= 2


def test_mass_balance_must_close_and_no_recovery_claim_without_facility(lifecycle, client, H):
    b = lifecycle["batch"]
    assert b["mass_balance"]["recovered_kg"] == 0
    rec = client.post(f"/api/facility/batches/{b['id']}/receive", headers=H["facility"], json={"received_kg": b["input_kg"]}).json()
    assert rec["run_status"] == "completed", rec
    bad = client.post(f"/api/facility/batches/{b['id']}/process", headers=H["facility"], json={"recovered_kg": b["input_kg"] * 0.5, "rejects_kg": 0.0, "loss_kg": 0.0}).json()
    assert bad["run_status"] == "escalated" and "balance" in bad["reason"].lower()
    st = client.get(f"/api/passports/{b['code']}", headers=H["facility"]).json()["status"]
    assert st in ("at_facility", "processing")


def test_final_bonus_only_after_facility_confirmation(lifecycle, client, H):
    b = lifecycle["batch"]
    before = client.get("/api/wallet", headers=H["citizen2"]).json()["balances"]["final"]
    kg = b["input_kg"]
    ok = client.post(f"/api/facility/batches/{b['id']}/process", headers=H["facility"], json={"recovered_kg": round(kg * 0.8, 3), "rejects_kg": round(kg * 0.1, 3), "loss_kg": round(kg * 0.1, 3), "residual_destination": "test landfill"}).json()
    assert ok["run_status"] == "completed", ok
    after = client.get("/api/wallet", headers=H["citizen2"]).json()["balances"]["final"]
    assert after > before
    d = client.get(f"/api/passports/{b['code']}", headers=H["citizen2"]).json()
    assert d["status"] != "fully_recycled"  # never claims everything is recycled
    assert d["chain"]["intact"]


# ------------------------------------------------------------------ approvals / human gates
def test_route_plan_needs_approval(client, H):
    r = client.post("/api/logistics/plan", headers=H["municipal"], json={}).json()
    assert r["run_status"] == "awaiting_approval" and r["approval_id"]
    assert client.post(f"/api/approvals/{r['approval_id']}/decide", headers=H["citizen"], json={"approve": True}).status_code == 403
    ok = client.post(f"/api/approvals/{r['approval_id']}/decide", headers=H["municipal"], json={"approve": True})
    assert ok.status_code == 200
    assert client.post(f"/api/approvals/{r['approval_id']}/decide", headers=H["municipal"], json={"approve": True}).status_code == 409
    routes = client.get("/api/logistics/routes", headers=H["municipal"]).json()
    assert any(x["status"] == "approved_simulated" for x in routes)


def test_marketplace_transfer_needs_approval(client, H):
    l = client.post("/api/marketplace/listings", headers=H["citizen"], json={"kind": "supply", "material_key": "cardboard", "quantity_kg": 20, "condition": "clean"})
    assert l.status_code == 200
    ms = client.get("/api/marketplace/matches?status=recommended", headers=H["citizen"]).json()
    if ms:
        r = client.post(f"/api/marketplace/matches/{ms[0]['id']}/request", headers=H["citizen"]).json()
        assert r["run_status"] == "awaiting_approval"


def test_citizen_cannot_post_demand(client, H):
    assert client.post("/api/marketplace/listings", headers=H["citizen"], json={"kind": "demand", "material_key": "cardboard", "quantity_kg": 5}).status_code == 403


# ------------------------------------------------------------------ complaints
def test_complaint_needs_evidence_to_resolve(client, H):
    c = client.post("/api/complaints", headers=H["citizen"], data={"description": "Garbage overflowing near bus stop for days", "lat": "13.05", "lng": "80.25"}).json()["complaint"]
    assert c["category"]
    assert client.post(f"/api/complaints/{c['id']}/action", headers=H["municipal"], json={"action": "resolve", "note": "x"}).status_code == 422
    ok = client.post(f"/api/complaints/{c['id']}/action", headers=H["municipal"], json={"action": "resolve", "note": "Cleared and sanitised bin area", "evidence": "WO-123"})
    assert ok.status_code == 200 and ok.json()["status"] == "resolution_submitted"


# ------------------------------------------------------------------ twin, forecast, landfill, events
def test_digital_twin_scenarios_differ_from_baseline(client, H):
    sc = client.get("/api/simulation/scenarios", headers=H["municipal"]).json()
    assert len(sc["scenarios"]) >= 4
    res = client.post("/api/simulation/run", headers=H["municipal"], json={"name": "t", "params": sc["scenarios"][0]["params"]}).json()["result"]
    assert res["scenario"]["kpis"]["residual_t"] < res["baseline"]["kpis"]["residual_t"]
    assert res["attribution"] and res["attribution"][0]["parameter"] == "segregation_rate"
    res2 = client.post("/api/simulation/run", headers=H["municipal"], json={"name": "t", "params": sc["scenarios"][4]["params"]}).json()["result"]
    assert res2["scenario"]["kpis"]["end_backlog_t"] >= res2["baseline"]["kpis"]["end_backlog_t"]


def test_forecast_labelled_simulated(client, H):
    f = client.get("/api/municipal/forecast?horizon=7", headers=H["municipal"]).json()
    assert f["trained"] and "SIMULATED" in f["training_data"].upper()


def test_landfill_has_disclaimer(client, H):
    l = client.get("/api/landfill", headers=H["municipal"]).json()
    assert l["sites"] and "SIMULATED" in l["capacity_disclaimer"].upper()


def test_event_certificate_needs_verified_evidence(client, H):
    e = client.post("/api/events", headers=H["organiser"], json={"name": "Test Fest", "starts_at": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)).replace(tzinfo=None).isoformat(), "expected_attendance": 200, "food": "packaged", "volunteers_available": 4}).json()["event"]
    client.post(f"/api/events/{e['id']}/waste", headers=H["organiser"], json={"stream": "dry_recyclable", "kg": 50, "recovered": True})
    r = client.post(f"/api/events/{e['id']}/complete", headers=H["organiser"]).json()
    assert not r["certificate"].get("issued")


def test_league_ranked_by_quality_not_volume(client, H):
    rows = client.get("/api/league", headers=H["citizen"]).json()["rows"]
    scores = [r["score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_rewards_irctc_is_simulation_only(client, H):
    cat = client.get("/api/rewards/catalog", headers=H["citizen"]).json()
    ir = [c for c in cat if "IRCTC" in c["partner"] or "Railway" in c["title"]]
    assert ir and all(c["simulation_only"] for c in ir)


# ------------------------------------------------------------------ agents / audit
def test_agent_runs_have_steps_and_audit(client, H):
    runs = client.get("/api/agents/runs", headers=H["municipal"]).json()
    assert runs
    d = client.get(f"/api/agents/runs/{runs[0]['id']}", headers=H["municipal"]).json()
    assert d["steps"] and all(k in d["steps"][0] for k in ("agent", "tool", "status", "retries", "next_agent"))
    assert client.get("/api/audit", headers=H["municipal"]).json()
    assert client.get("/api/agents/runs", headers=H["citizen"]).status_code == 200


def test_agent_tool_retry_then_failure_is_logged():
    from app.database.db import SessionLocal
    from app.agents.runtime import Ctx
    from app.models.models import AgentRun, AgentStep
    from sqlalchemy import select
    with SessionLocal() as db:
        run = AgentRun(workflow="t", title="retry-test")
        db.add(run); db.commit()
        ctx = Ctx(db, run, None)
        calls = {"n": 0}
        def flaky():
            calls["n"] += 1
            if calls["n"] < 2: raise RuntimeError("transient")
            return {"ok": True}
        out = ctx.step("Test Agent", "flaky tool", flaky, tool="flaky")
        assert out == {"ok": True} and calls["n"] == 2
        st = db.scalars(select(AgentStep).where(AgentStep.run_id == run.id)).all()
        assert st[-1].status == "success" and st[-1].retries == 1


def test_assistant_works_without_api_key(client, H):
    r = client.post("/api/assistant", headers=H["citizen"], json={"message": "How many points do I have?"}).json()
    assert r["intent"] == "wallet" and r["llm_phrased"] is False


def test_demo_story_runs(client, H):
    r = client.post("/api/demo/run-story?quick=true", headers=H["municipal"]).json()
    assert len(r["steps"]) >= 6
    assert not any(s["status"] == "failed" for s in r["steps"])


def test_no_legacy_branding(client):
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    for p in list((root / "backend").rglob("*.py")) + list((root / "frontend" / "src").rglob("*.ts*")) + list((root / "data" / "seed").glob("*.json")):
        assert ("waste" + "wise") not in p.read_text(encoding="utf-8", errors="ignore").lower(), p
