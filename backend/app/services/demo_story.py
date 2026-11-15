"""Guided demonstration: executes the connected VYARTHX story through the real orchestrator and workflows."""
from __future__ import annotations

import io
import random

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import workflows  # noqa: F401  (register workflows)
from ..agents.runtime import run_workflow
from ..models.models import Batch, CollectionRequest, Facility, Household, MarketListing, Ward, User, now


def synthetic_image(seed: int | None = None, color=(168, 120, 70)) -> bytes:
    """A generated placeholder 'cardboard-coloured' image (NOT a real photograph). Unique per call so duplicate checks do not fire."""
    rng = random.Random(seed or random.randint(1, 10**9))
    im = Image.new("RGB", (480, 360), color)
    d = ImageDraw.Draw(im)
    for _ in range(40):
        x, y = rng.randint(0, 480), rng.randint(0, 360)
        d.rectangle([x, y, x + rng.randint(10, 90), y + rng.randint(4, 40)], outline=(120 + rng.randint(0, 40), 80, 40), width=2)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=85)
    return b.getvalue()


def _u(db, email):
    return db.scalars(select(User).where(User.email == email)).first()


def run_story(db: Session, label: str = "Guided demo", quick: bool = False) -> dict:
    """Citizen → agents → collector → facility → municipal. Returns the step list shown in the UI."""
    citizen, worker, facility, mun, org = (_u(db, e) for e in ("citizen@vyarthx.demo", "worker@vyarthx.demo", "facility@vyarthx.demo", "municipal@vyarthx.demo", "organiser@vyarthx.demo"))
    story: list[dict] = []

    def add(title, res):
        story.append({"title": title, "run_id": res["run_id"], "status": res["status"], "summary": res["summary"]})
        return res

    r1 = add("1. Citizen records a cardboard handover — Segregation, Verification, Reward and Logistics agents run",
             run_workflow(db, "waste_submission", {"image_bytes": synthetic_image(), "filename": "cardboard_box.jpg", "text": "cardboard packaging, clean and flattened", "est_weight_kg": 2.5}, citizen,
                          title=f"{label}: cardboard handover"))
    sid = r1["data"].get("submission_id")
    r2 = add("2. Citizen confirms the pickup — Logistics Agent matches a collector and facility",
             run_workflow(db, "schedule_pickup", {"submission_id": sid}, citizen, title=f"{label}: schedule pickup"))
    cid = r2["data"].get("collection_id")
    col = db.get(CollectionRequest, cid) if cid else None
    hh = db.get(Household, col.household_id) if col and col.household_id else None
    r3 = add("3. Collector confirms the handover (QR + weight) — Verification, Reward, Passport, Marketplace, Behaviour and Municipal agents run",
             run_workflow(db, "collection_confirm", {"collection_id": cid, "qr_code": hh.code if hh else "", "weight_kg": 2.5, "weight_source": "manual_entry", "evidence_note": "Weighed on hand scale (demo)"}, worker,
                          title=f"{label}: collector confirms handover"))
    batch_id = r3["data"].get("passport", {}).get("batch_id")
    if batch_id:
        add("4. MRF operator confirms receipt — Waste Passport updated",
            run_workflow(db, "facility_receive", {"batch_id": batch_id, "received_kg": 2.45, "note": "Received, bale intact"}, facility, title=f"{label}: facility receipt"))
        add("5. MRF operator records sorting — recovery, rejects and residual; final bonus credited; recovered material listed for recyclers",
            run_workflow(db, "facility_process", {"batch_id": batch_id, "recovered_kg": 1.8, "rejects_kg": 0.5, "loss_kg": 0.15, "other_kg": 0.0, "residual_kg": 0.5,
                                                   "residual_destination": "Perungudi dumpsite (simulated record)", "note": "Moisture + rejects recorded"}, facility, title=f"{label}: processing"))
    ward = db.scalars(select(Ward).where(Ward.name == "Kodungaiyur")).first()
    add("6. Citizen reports garbage — Citizen Reporting Agent classifies, checks duplicates and routes to the ward",
        run_workflow(db, "complaint_report", {"description": "Garbage heap overflowing near the bus stop, smells bad", "source": "text", "lat": ward.lat + 0.001, "lng": ward.lng + 0.001}, citizen,
                     title=f"{label}: garbage report"))
    add("7. Municipal planner runs Dynamic Collection — OR-Tools proposes routes; dispatch waits for approval",
        run_workflow(db, "route_plan", {"ward_ids": None}, mun, title=f"{label}: route plan (awaiting approval)"))
    from ..simulation import twin

    sc = twin.predefined(db)[0]
    add("8. Municipal Intelligence Agent runs the Digital Twin: 30% more households segregate",
        run_workflow(db, "digital_twin", {"name": sc["name"], "params": sc["params"]}, mun, title=f"{label}: digital twin"))
    return {"steps": story, "created_at": now().isoformat(), "note": "All records created by this story are labelled simulated (DEMO_MODE)."}
