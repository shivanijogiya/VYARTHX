"""Seed data for the VYARTHX Tamil Nadu (Greater Chennai) pilot configuration.

HONESTY NOTE: every record seeded here is SIMULATED demonstration data. Ward names are real Chennai localities used as
approximate centroids (not official ward boundaries); populations, capacities, vehicles, facilities, users and history are
invented. No personal data of real people is used. Official datasets (CPCB, data.gov.in, OpenCity, TNPCB) were NOT
retrieved in the build environment — see data/sources/registry.json.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..core.security import hash_password
from ..models import models as M
from ..models.models import now
from ..services import community, complaints as cmp, events as evs, passport as pp, rewards, circular
from ..services.common import get_cfg

DEMO_PASSWORD = "Vyarthx@2026"
SIM = "simulated"

WARDS = [  # name, zone, lat, lng, population(simulated)
    ("T. Nagar", "Teynampet", 13.0418, 80.2341, 32000), ("Velachery", "Adyar", 12.9815, 80.2180, 28000), ("Anna Nagar", "Anna Nagar", 13.0850, 80.2101, 26000),
    ("Adyar", "Adyar", 13.0012, 80.2565, 24500), ("Tondiarpet", "Tondiarpet", 13.1270, 80.2890, 23000), ("Kodungaiyur", "Tiruvottiyur", 13.1330, 80.2530, 22000),
    ("Ambattur", "Ambattur", 13.1143, 80.1548, 21000), ("Perungudi", "Perungudi", 12.9650, 80.2461, 20000), ("Royapuram", "Royapuram", 13.1130, 80.2950, 19000),
    ("Sholinganallur", "Sholinganallur", 12.9010, 80.2279, 18500), ("Guindy", "Alandur", 13.0067, 80.2206, 18000), ("Mylapore", "Teynampet", 13.0368, 80.2676, 17000),
    ("Perambur", "Madhavaram", 13.1186, 80.2330, 16000), ("Kilpauk", "Anna Nagar", 13.0836, 80.2420, 15000), ("Besant Nagar", "Adyar", 13.0003, 80.2667, 13000),
]
WARD_NOTE = "Real Chennai locality name used as an APPROXIMATE centroid; not an official ward boundary. Population is a simulated placeholder."

ALL_MATS = ["cardboard", "paper", "pet", "hdpe", "plastic_film", "metal", "glass", "tetrapak", "textile", "mixed", "furniture"]
FACILITIES = [  # name, type, ward, cap, load, accepts, authorised, note
    ("Demo MRF – Perungudi (illustrative)", "mrf", "Perungudi", 12, 7.8, ALL_MATS, True),
    ("Demo MRF – Kodungaiyur (illustrative)", "mrf", "Kodungaiyur", 11, 7.2, ALL_MATS, True),
    ("Demo MRF – Ambattur (illustrative)", "mrf", "Ambattur", 7, 4.5, ALL_MATS, True),
    ("Demo Recycler – Manali (simulated)", "recycler", "Tondiarpet", 15, 9, ["cardboard", "paper", "pet", "hdpe", "metal", "glass", "tetrapak"], True),
    ("Demo Recycler – Guindy (simulated)", "recycler", "Guindy", 10, 5, ["metal", "pet", "hdpe", "glass"], True),
    ("Demo Plastic Recycler – Ambattur (simulated)", "recycler", "Ambattur", 8, 4, ["pet", "hdpe", "plastic_film"], True),
    ("Demo Micro-Composting Centre – Adyar", "compost", "Adyar", 4, 3.2, ["organic"], True),
    ("Demo Windrow Compost Plant – Velachery", "compost", "Velachery", 18, 15.5, ["organic"], True),
    ("Demo Vermicompost Unit – Anna Nagar", "vermicompost", "Anna Nagar", 2, 1.4, ["organic"], True),
    ("Demo Biomethanation Plant – Perungudi", "biomethanation", "Perungudi", 12, 10.2, ["organic"], True),
    ("Demo Special-Care Collection Point – T. Nagar", "special_care", "T. Nagar", 1.5, 0.3, ["special", "mixed"], True),
    ("Demo Authorised E-waste Recycler – Guindy", "ewaste", "Guindy", 3, 1.0, ["ewaste", "special"], True),
    ("Demo E-waste Collection Centre – Anna Nagar (PENDING approval)", "ewaste", "Anna Nagar", 1, 0, ["ewaste"], False),
    ("Demo Community NGO – Mylapore", "ngo", "Mylapore", 1, 0.2, ["textile", "furniture", "reusable"], True),
    ("Demo Refurbishment Workshop – Ambattur", "refurbisher", "Ambattur", 1, 0.2, ["furniture", "ewaste", "reusable"], True),
    ("Demo Government School – Anna Nagar", "school", "Anna Nagar", 0.5, 0, ["furniture", "reusable", "books"], True),
    ("Demo Nursery & Garden Centre – Besant Nagar", "nursery", "Besant Nagar", 1, 0.2, ["compost"], True),
]
PEOPLE = [  # email, name, role, ward
    ("citizen@vyarthx.demo", "Ananya R. (demo citizen)", "citizen", "Adyar"), ("citizen2@vyarthx.demo", "Karthik S. (demo citizen)", "citizen", "Anna Nagar"),
    ("worker@vyarthx.demo", "Murugan K. (demo worker)", "worker", "Adyar"), ("worker2@vyarthx.demo", "Lakshmi P. (demo worker)", "worker", "Anna Nagar"),
    ("municipal@vyarthx.demo", "Meenakshi V. (demo ward officer)", "municipal", "Adyar"), ("facility@vyarthx.demo", "MRF Operator – Perungudi (demo)", "facility", "Perungudi"),
    ("compostops@vyarthx.demo", "Compost Plant Operator – Velachery (demo)", "facility", "Velachery"), ("recycler@vyarthx.demo", "Recycler Desk – Manali (demo)", "recycler", "Tondiarpet"),
    ("nursery@vyarthx.demo", "Nursery Buyer – Besant Nagar (demo)", "recycler", "Besant Nagar"), ("organiser@vyarthx.demo", "College Event Organiser (demo)", "organiser", "Guindy"),
]
COMMUNITIES = [  # name, type, ward, members, seg, part, contam, handover, points
    ("Lakeview Apartments (demo)", "apartment", "Adyar", 220, 0.78, 0.71, 0.09, 0.88, 5400), ("Greenfield Residency (demo)", "apartment", "Anna Nagar", 180, 0.71, 0.66, 0.13, 0.84, 4300),
    ("Sunrise Towers (demo)", "apartment", "Velachery", 260, 0.58, 0.52, 0.24, 0.73, 3100), ("Harbour View Society (demo)", "apartment", "Royapuram", 140, 0.49, 0.44, 0.31, 0.66, 1900),
    ("Demo College of Engineering", "college", "Guindy", 2400, 0.69, 0.58, 0.17, 0.80, 7200), ("Demo Arts & Science College", "college", "Mylapore", 1800, 0.62, 0.50, 0.21, 0.75, 4800),
    ("TechPark Block A (demo office)", "office", "Sholinganallur", 900, 0.55, 0.40, 0.26, 0.70, 2500), ("Demo Public School – Perambur", "school", "Perambur", 700, 0.66, 0.61, 0.15, 0.82, 2200),
    ("Ward: Adyar (demo)", "ward", "Adyar", 24500, 0.52, 0.37, 0.22, 0.74, 9800), ("Ward: Anna Nagar (demo)", "ward", "Anna Nagar", 26000, 0.47, 0.33, 0.27, 0.69, 8100),
]
CATALOG = [  # partner, title, category, scope, cost, eligibility, integration, min_level
    ("City bus operator (concept)", "Bus-pass credit ₹100 — concept", "transport", "partner", 500, "Requires transport authority agreement", "Not integrated — simulated voucher", 0),
    ("Proposed Indian Railways / IRCTC Partnership — Simulation Only", "Rail travel concession voucher — Simulation Only", "rail", "partner", 1500, "Illustrative only. No agreement with Indian Railways / IRCTC exists.", "Not integrated — architecture placeholder for a future authorised voucher API", 2),
    ("City metro / MTC card (concept)", "Transit-card top-up ₹50 — concept", "transport", "partner", 300, "Requires city transport authority agreement", "Not integrated — simulated voucher", 0),
    ("Municipal service credit (concept)", "Municipal service-fee credit — concept", "municipal", "partner", 800, "Requires municipal approval; no real benefit is issued", "Not integrated — simulated voucher", 1),
    ("Local eco-store (demo partner)", "Reusable steel bottle voucher — demo", "local", "partner", 300, "Demo partner; no onboarding exists", "Not integrated — simulated voucher", 0),
    ("Local eco-store (demo partner)", "10% off refill-store purchase — demo", "local", "partner", 150, "Demo partner; no onboarding exists", "Not integrated — simulated voucher", 0),
    ("Community pool (demo)", "Society composting bin sponsorship — community reward", "community", "community", 2000, "Pooled community points", "Sponsor/municipal funding required", 0),
    ("Education partner (demo)", "Sustainability workshop seat — demo", "education", "partner", 250, "Requires institutional participation", "Not integrated — simulated voucher", 0),
    ("Community pool (demo)", "Garden tool kit for the neighbourhood — community reward", "community", "community", 1200, "Pooled community points", "Sponsor/municipal funding required", 0),
]


def _jit(rng, v, s=0.004):
    return v + rng.uniform(-s, s)


def _backdate(db: Session, user_id: int, since_id: int, ts: datetime) -> None:
    db.execute(update(M.RewardTransaction).where(M.RewardTransaction.user_id == user_id, M.RewardTransaction.id > since_id).values(created_at=ts))


def _alloc_vehicles(pops: list[int], n: int) -> list[int]:
    tot = sum(pops)
    raw = [p / tot * n for p in pops]
    base = [max(1, int(math.floor(r))) for r in raw]
    while sum(base) < n:
        i = max(range(len(raw)), key=lambda k: raw[k] - base[k])
        base[i] += 1
    while sum(base) > n:
        i = max(range(len(raw)), key=lambda k: base[k] - raw[k])
        if base[i] > 1:
            base[i] -= 1
        else:
            break
    return base


def reset_schema(db: Session) -> None:
    from .db import engine, Base

    db.close()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed_all(db: Session) -> dict:
    rng = random.Random(2026)
    npr = np.random.default_rng(2026)
    # ---- wards
    wards = {}
    for n, z, la, lo, pop in WARDS:
        w = M.Ward(name=n, zone=z, lat=la, lng=lo, population=pop, data_class=SIM, source_note=WARD_NOTE)
        db.add(w)
        wards[n] = w
    db.flush()
    # ---- facilities
    facs: dict[str, M.Facility] = {}
    for name, ft, wn, cap, load, acc, auth in FACILITIES:
        w = wards[wn]
        f = M.Facility(name=name, type=ft, ward_id=w.id, lat=_jit(rng, w.lat, 0.006), lng=_jit(rng, w.lng, 0.006), capacity_tpd=cap, load_tpd=load, accepts=acc, authorised=auth,
                       authorisation_note="Demo record — NOT an official authorisation" if auth else "Pending municipal approval in VYARTHX (demo)", capacity_class=SIM, data_class=SIM,
                       source_note="Illustrative placement near a real locality; capacity and load are simulated. Official facility registers were not retrieved.",
                       meta={"repair_skills": ["furniture", "electronics"]} if ft == "refurbisher" else {})
        db.add(f)
        facs[name] = f
    for name, wn, rep, rem, share in [("Kodungaiyur dumpsite (name only — capacity SIMULATED)", "Kodungaiyur", 1_000_000, 250_000, 0.55),
                                       ("Perungudi dumpsite (name only — capacity SIMULATED)", "Perungudi", 800_000, 200_000, 0.45)]:
        w = wards[wn]
        db.add(M.Facility(name=name, type="dumpsite", ward_id=w.id, lat=w.lat + 0.01, lng=w.lng + 0.012, capacity_tpd=0, authorised=True, reported_capacity_t=rep, remaining_capacity_t=rem,
                          capacity_class=SIM, data_class=SIM, authorisation_note="Existing dumpsite locality — capacity figures are SIMULATED placeholders",
                          source_note="Official capacity data was not retrieved (CPCB / TNPCB / GCC). Do not cite these numbers.", meta={"inflow_share": share}))
    db.flush()
    # ---- vehicles
    order = [w.name for w in sorted(wards.values(), key=lambda w: w.id)]
    alloc = _alloc_vehicles([wards[n].population for n in order], 30)
    k = 1
    for n, c in zip(order, alloc):
        for _ in range(c):
            w = wards[n]
            db.add(M.Vehicle(code=f"VX-V{k:02d}", capacity_kg=3000, ward_id=w.id, status="available", lat=_jit(rng, w.lat), lng=_jit(rng, w.lng), gps_connected=False, data_class=SIM))
            k += 1
    # ---- communities
    comms = {}
    for n, t, wn, mem, seg, part, con, han, pts in COMMUNITIES:
        c = M.Community(name=n, type=t, ward_id=wards[wn].id, members_base=mem, base_seg_rate=seg, base_participation=part, base_contamination=con, base_handover=han, base_points=pts, data_class=SIM)
        db.add(c)
        comms[n] = c
    db.flush()
    # ---- users, households, workers
    pw = hash_password(DEMO_PASSWORD)
    users: dict[str, M.User] = {}
    fac_for = {"facility@vyarthx.demo": "Demo MRF – Perungudi (illustrative)", "compostops@vyarthx.demo": "Demo Windrow Compost Plant – Velachery",
               "recycler@vyarthx.demo": "Demo Recycler – Manali (simulated)", "nursery@vyarthx.demo": "Demo Nursery & Garden Centre – Besant Nagar"}
    comm_for = {"citizen@vyarthx.demo": "Lakeview Apartments (demo)", "citizen2@vyarthx.demo": "Greenfield Residency (demo)", "organiser@vyarthx.demo": "Demo College of Engineering"}
    for email, name, role, wn in PEOPLE:
        u = M.User(email=email, name=name, role=role, password_hash=pw, ward_id=wards[wn].id, language="ta" if email == "citizen2@vyarthx.demo" else "en", data_class=SIM,
                   facility_id=facs[fac_for[email]].id if email in fac_for else None, community_id=comms[comm_for[email]].id if email in comm_for else None,
                   prefs={"notifications": {"enabled": True, "max_per_day": 6, "reminders": True, "reward": True, "task": True, "pickup": True}, "goals": {"weekly_submissions": 3}})
        db.add(u)
        users[email] = u
    extra_citizens = []
    cnames = list(comms.keys())[:4]
    for i in range(1, 11):
        wn = order[i % len(order)]
        u = M.User(email=f"household{i:02d}@vyarthx.demo", name=f"Demo Household {i:02d}", role="citizen", password_hash=pw, ward_id=wards[wn].id, data_class=SIM,
                   community_id=comms[cnames[i % len(cnames)]].id, prefs={"notifications": {"enabled": True, "max_per_day": 6}})
        db.add(u)
        extra_citizens.append(u)
    db.flush()
    hh_by_user: dict[int, M.Household] = {}
    for idx, u in enumerate([users["citizen@vyarthx.demo"], users["citizen2@vyarthx.demo"]] + extra_citizens, start=1):
        w = db.get(M.Ward, u.ward_id)
        h = M.Household(user_id=u.id, code=f"VX-HH-{idx:04d}", address=f"Demo address {idx}, {w.name} (simulated)", ward_id=w.id, lat=_jit(rng, w.lat), lng=_jit(rng, w.lng), data_class=SIM)
        db.add(h)
        hh_by_user[u.id] = h
    workers = {}
    for idx, (email, trained) in enumerate([("worker@vyarthx.demo", ["safe_handling", "special_care"]), ("worker2@vyarthx.demo", ["safe_handling"])], start=1):
        u = users[email]
        w = db.get(M.Ward, u.ward_id)
        wk = M.Worker(user_id=u.id, worker_code=f"WRK-{idx:03d}", ward_id=w.id, identity_status="optional_unverified", onboarding_partner="Demo NGO onboarding partner (simulated)",
                      lat=w.lat, lng=w.lng, capacity_kg=200, languages=["Tamil", "English"], training=trained, data_class=SIM)
        db.add(wk)
        workers[email] = wk
    for idx, wn in enumerate(["T. Nagar", "Velachery", "Perungudi", "Kodungaiyur"], start=3):
        u = M.User(email=f"collector{idx:02d}@vyarthx.demo", name=f"Demo Collector {idx:02d}", role="worker", password_hash=pw, ward_id=wards[wn].id, data_class=SIM)
        db.add(u)
        db.flush()
        db.add(M.Worker(user_id=u.id, worker_code=f"WRK-{idx:03d}", ward_id=wards[wn].id, lat=wards[wn].lat, lng=wards[wn].lng, capacity_kg=180, languages=["Tamil"],
                        training=["safe_handling"] + (["special_care"] if idx == 4 else []), data_class=SIM))
    db.flush()
    # ---- catalog, challenges
    for p, t, cat, scope, cost, el, integ, lvl in CATALOG:
        db.add(M.RewardCatalog(partner=p, title=t, category=cat, scope=scope, points_cost=cost, eligibility=el, integration_status=integ, simulation_only=True, min_level=lvl))
    t0 = now()
    chs = [("Seven-Day Segregation Challenge", "weekly", "Hand over 5 verified segregated collections in a week.", "verified_submissions", 5, 40, None),
           ("Zero-Contamination Week", "weekly", "Four clean handovers with no contamination flags.", "verified_submissions", 4, 30, None),
           ("E-Waste Collection Drive", "monthly", "Hand over 2 special-care / e-waste items to authorised collection.", "ewaste", 2, 60, None),
           ("Community Compost Challenge", "monthly", "Four verified wet-waste handovers for composting.", "compost", 4, 50, None),
           ("Reuse Before Replace", "monthly", "Transfer one item through the Reuse Exchange.", "reuse", 1, 35, None),
           ("Campus Green Month", "monthly", "Campus-wide verified handovers.", "verified_submissions", 6, 80, "Demo College of Engineering")]
    for t, cad, desc, rule, tgt, pts, cn in chs:
        db.add(M.Challenge(title=t, cadence=cad, description=desc, rule=rule, target=tgt, points_reward=pts, starts_at=t0 - timedelta(days=2), ends_at=t0 + timedelta(days=5 if cad == "weekly" else 26),
                           community_id=comms[cn].id if cn else None, data_class=SIM))
    db.flush()
    c1 = users["citizen@vyarthx.demo"]
    for ch in db.scalars(select(M.Challenge)).all()[:2]:
        db.add(M.ChallengeParticipation(challenge_id=ch.id, user_id=c1.id, progress=2))
    # ---- ward_daily baseline (simulated), consistent with the digital-twin assumptions
    days = 90
    last = (t0 - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    wk_f = [1.04, 1.0, 0.98, 0.98, 1.0, 1.05, 1.12]
    seg_w = {w.id: float(np.clip(0.42 + npr.normal(0, 0.07), 0.28, 0.58)) for w in wards.values()}
    eff_w = {w.id: float(np.clip(0.88 + npr.normal(0, 0.035), 0.80, 0.95)) for w in wards.values()}
    rows = []
    for w in wards.values():
        base = w.population * 0.55 / 1000
        for i in range(days):
            d = last - timedelta(days=days - 1 - i)
            fest = 1.35 if 40 <= i <= 43 else 1.0
            gen = base * wk_f[d.weekday()] * fest * (1 + npr.normal(0, 0.03))
            coll = gen * eff_w[w.id]
            seg = float(np.clip(seg_w[w.id] + 0.0008 * i, 0, 0.9))
            wet, dry, oth = coll * 0.5, coll * 0.32, coll * 0.18
            wet_s, dry_s = wet * seg, dry * seg
            comp = wet_s * 0.9 * 0.3
            drymat = dry_s * (1 - 0.12) * 0.88
            mixrec = dry * (1 - seg) * 0.06
            rec = comp + drymat + mixrec
            resid = oth + wet * (1 - seg) + dry * (1 - seg) - mixrec + wet_s * 0.1 + dry_s * (1 - (1 - 0.12) * 0.88)
            rows.append(M.WardDaily(ward_id=w.id, day=d, generated_t=round(gen, 3), collected_t=round(coll, 3), segregated_t=round(wet_s + dry_s, 3), processed_t=round(wet_s + dry_s, 3),
                                    recovered_t=round(rec, 3), residual_t=round(resid, 3), data_class=SIM))
    db.add_all(rows)
    db.commit()
    # ---- marketplace
    rec_u, nur_u, cmp_u = users["recycler@vyarthx.demo"], users["nursery@vyarthx.demo"], users["compostops@vyarthx.demo"]
    manali = facs["Demo Recycler – Manali (simulated)"]
    velach = facs["Demo Windrow Compost Plant – Velachery"]
    nursery = facs["Demo Nursery & Garden Centre – Besant Nagar"]

    def listing(user, kind, mat, qty, title, fac=None, ward="Adyar", cond="clean", cont="none", price=None, seller="household", ver="unverified", window="Weekdays 9-5"):
        w = wards[ward]
        x = M.MarketListing(user_id=user.id, facility_id=fac.id if fac else None, kind=kind, material_key=mat, title=title, quantity_kg=qty, remaining_kg=qty, condition=cond, contamination=cont,
                            lat=fac.lat if fac else _jit(rng, w.lat), lng=fac.lng if fac else _jit(rng, w.lng), ward_id=w.id, price_inr_per_kg=price,
                            price_source="user-entered, indicative only — no live market rate" if price else "not stated", seller_type=seller, verification=ver, pickup_window=window, data_class=SIM)
        db.add(x)
        return x

    listing(rec_u, "demand", "cardboard", 200, "Wanted: baled cardboard", manali, "Tondiarpet", seller="recycler", window="Mon-Sat 9-6")
    listing(rec_u, "demand", "pet", 100, "Wanted: PET bottles", manali, "Tondiarpet", seller="recycler")
    listing(rec_u, "demand", "metal", 50, "Wanted: aluminium / metal scrap", manali, "Tondiarpet", seller="recycler")
    listing(cmp_u, "demand", "organic", 2000, "Organic feedstock wanted — windrow plant", velach, "Velachery", seller="composting facility")
    listing(cmp_u, "supply", "compost", 800, "Finished compost (estimate — pending lab test)", velach, "Velachery", seller="composting facility", price=6.0, ver="facility_declared")
    listing(nur_u, "demand", "compost", 500, "Nursery wants compost", nursery, "Besant Nagar", seller="nursery")
    listing(users["worker@vyarthx.demo"], "supply", "cardboard", 120, "Cardboard bundles (collected)", None, "Adyar", seller="waste worker", price=7.0, ver="worker_declared")
    listing(c1, "supply", "paper", 60, "Society paper & newspaper", None, "Adyar", seller="society", cond="dry")
    listing(c1, "supply", "organic", 1500, "Society organic feedstock (≈100 households × 0.5 kg × 30 days)", None, "Adyar", seller="society", cond="segregated wet waste")
    listing(users["citizen2@vyarthx.demo"], "supply", "pet", 45, "Clean PET bottles", None, "Anna Nagar", seller="household")
    listing(users["worker2@vyarthx.demo"], "supply", "metal", 30, "Mixed metal / cans", None, "Anna Nagar", seller="waste worker", cont="possible")
    listing(users["worker2@vyarthx.demo"], "supply", "glass", 70, "Glass bottles", None, "Anna Nagar", seller="waste worker")
    listing(users["organiser@vyarthx.demo"], "supply", "ewaste", 25, "Campus e-waste lot", None, "Guindy", seller="college", cond="mixed electronics")
    db.commit()
    from ..services import marketplace as mk

    mk.recommend(db)
    # ---- history for citizens (collections, passports, rewards)
    mrf = facs["Demo MRF – Perungudi (illustrative)"]
    compost_f = facs["Demo Micro-Composting Centre – Adyar"]
    mats = [("cardboard", "dry", "cardboard", "Cardboard packaging", "Corrugated cardboard", "none"), ("pet", "dry", "pet_bottle", "PET plastic bottle", "PET plastic", "none"),
            ("organic", "wet", "food_waste", "Food / kitchen waste", "Organic (biodegradable)", "none"), ("paper", "dry", "paper", "Paper", "Paper", "none"),
            ("metal", "dry", "metal_can", "Metal can", "Aluminium / steel", "none"), ("glass", "dry", "glass_bottle", "Glass bottle / jar", "Glass", "none"),
            ("plastic_film", "dry", "plastic_wrapper", "Plastic wrapper / film", "Multilayer plastic film", "possible"), ("paper", "dry", "pizza_box", "Cardboard food packaging", "Paperboard (food-soiled)", "detected")]

    def history(u: M.User, wk: M.Worker, ago_days: float, kind_idx: int, state: str):
        mk_, stream, _, obj, mat, cont = mats[kind_idx % len(mats)]
        weight = round(rng.uniform(0.9, 4.2), 2)
        ts = t0 - timedelta(days=ago_days, hours=rng.randint(0, 3))
        hh = hh_by_user[u.id]
        before = db.scalar(select(func.coalesce(func.max(M.RewardTransaction.id), 0)))
        sub = M.Submission(user_id=u.id, household_id=hh.id, ward_id=hh.ward_id, detected_object=obj, material=mat, material_key=mk_, stream=stream, confidence=round(rng.uniform(0.72, 0.93), 2),
                           contamination=cont, est_weight_kg=round(weight * rng.uniform(0.85, 1.2), 2), status="collected", description="(seeded history)", created_at=ts - timedelta(hours=5),
                           classification={"reward_eligible": True, "reward_note": "seeded"}, verification={"flags": [], "risk": 0.0}, data_class=SIM)
        db.add(sub)
        db.flush()
        rewards.provisional_award(db, u.id, sub)
        col = M.CollectionRequest(submission_id=sub.id, user_id=u.id, household_id=hh.id, ward_id=hh.ward_id, worker_id=wk.id, kind="household", stream=stream, material_key=mk_, status="collected",
                                  est_weight_kg=sub.est_weight_kg, verified_weight_kg=weight, weight_source="manual_entry", lat=hh.lat, lng=hh.lng, scheduled_for=ts, accepted_at=ts - timedelta(hours=2),
                                  collected_at=ts, qr_verified=True, evidence={"qr": "match", "flags": []}, data_class=SIM, created_at=ts - timedelta(hours=4))
        db.add(col)
        db.flush()
        rewards.verified_award(db, col, weight, cont)
        b = pp.create_batch(db, col, material=mat)
        b.input_kg, b.status, b.created_at = weight, "collected", ts
        pp.add_event(db, b, "household", "Segregated waste recorded", u.name, "citizen", db.get(M.Ward, hh.ward_id).name, sub.est_weight_kg, "recorded", ts=ts - timedelta(hours=5), meta={"stream": stream})
        pp.add_event(db, b, "collector", "Pickup confirmed by collector", wk.worker_code, "worker", db.get(M.Ward, hh.ward_id).name, weight, "verified", evidence="QR match; manual_entry", ts=ts)
        db.add(M.WorkerPayment(worker_id=wk.id, collection_id=col.id, amount_inr=max(10.0, round(weight * 3.0, 2)), note="Collection fee (simulated record)", created_at=ts))
        if state in ("at_facility", "processed"):
            f = compost_f if stream == "wet" else mrf
            b.current_facility_id, b.status, col.status, col.facility_id = f.id, "at_facility", "delivered", f.id
            pp.add_event(db, b, "mrf", "Batch received at facility", f.name, "facility", f.name, weight, "verified", ts=ts + timedelta(hours=7))
        if state == "processed":
            rate = 0.78 if stream == "dry" else 0.9
            rec = round(weight * rate * (0.6 if cont != "none" else 1.0), 2)
            rej = round(weight * 0.12 + (weight - rec) * 0.0, 2)
            loss = round(weight - rec - rej, 2) if stream == "wet" else 0.0
            oth = 0.0
            if stream != "wet":
                rej = round(weight - rec, 2)
            pr = M.ProcessingRecord(batch_id=b.id, facility_id=b.current_facility_id, process="sorting", input_kg=weight, recovered_kg=rec, rejects_kg=rej, loss_kg=max(loss, 0), other_kg=oth,
                                    residual_kg=rej, confirmed_by=None, data_class=SIM, created_at=ts + timedelta(days=1))
            db.add(pr)
            db.flush()
            b.recovered_kg, b.rejects_kg, b.loss_kg, b.other_kg, b.residual_kg = rec, rej, max(loss, 0), oth, rej
            b.residual_destination = "Perungudi dumpsite (simulated record)"
            b.status = pp.final_status(b)
            col.status, sub.status = "completed", "completed"
            pp.add_event(db, b, "mrf", "Sorting / processing record", db.get(M.Facility, b.current_facility_id).name, "facility", "", rec, "verified", ts=ts + timedelta(days=1), meta={"recovered_kg": rec, "rejects_kg": rej})
            pp.add_event(db, b, "residual", "Residual handling recorded", "Facility", "facility", b.residual_destination, rej, "recorded", ts=ts + timedelta(days=1, hours=2))
            mbf = pp.mass_balance(b)
            pp.add_event(db, b, "final", f"Final status: {pp.STATUS_TEXT[b.status]}", "Facility", "facility", "", weight, "verified", ts=ts + timedelta(days=1, hours=3), meta={"mass_balance": mbf})
            rewards.final_award(db, u.id, b.id, pr.id, mk_, rec)
        _backdate(db, u.id, before, ts)
        return b

    w1, w2 = workers["worker@vyarthx.demo"], workers["worker2@vyarthx.demo"]
    plan1 = [29, 26, 24, 21, 19, 16, 14, 12, 10, 8, 6, 4, 3, 2, 1]
    for i, d in enumerate(plan1):
        state = "processed" if d >= 8 else ("at_facility" if d in (4, 3) else "none")
        history(c1, w1, d, i, state)
    for i, d in enumerate([27, 20, 13, 9, 5, 2]):
        history(users["citizen2@vyarthx.demo"], w2, d, i + 3, "processed" if d >= 9 else "none")
    for j, u in enumerate(extra_citizens):
        for i, d in enumerate(sorted(rng.sample(range(1, 28), 3 + j % 4), reverse=True)):
            history(u, w1 if j % 2 == 0 else w2, d, i + j, "processed" if d > 10 else "none")
    db.commit()
    # ---- open pickups (today/tomorrow) for the worker portal
    for u, wk, st, kind in [(c1, w1, "assigned", 0), (users["citizen2@vyarthx.demo"], w2, "assigned", 1)]:
        hh = hh_by_user[u.id]
        mk_, stream, _, obj, mat, cont = mats[kind]
        sub = M.Submission(user_id=u.id, household_id=hh.id, ward_id=hh.ward_id, detected_object=obj, material=mat, material_key=mk_, stream=stream, confidence=0.84, contamination=cont, est_weight_kg=2.5,
                           status="scheduled", description="(seeded upcoming pickup)", classification={"reward_eligible": True}, verification={"flags": []}, data_class=SIM)
        db.add(sub)
        db.flush()
        rewards.provisional_award(db, u.id, sub)
        db.add(M.CollectionRequest(submission_id=sub.id, user_id=u.id, household_id=hh.id, ward_id=hh.ward_id, worker_id=wk.id, suggested_worker_id=wk.id, kind="household", stream=stream, material_key=mk_,
                                   status=st, est_weight_kg=2.5, lat=hh.lat, lng=hh.lng, scheduled_for=t0 + timedelta(hours=18), data_class=SIM))
    for wn, mk_, stream in [("Velachery", "paper", "dry"), ("T. Nagar", "organic", "wet"), ("Guindy", "pet", "dry")]:
        w = wards[wn]
        u = extra_citizens[rng.randrange(len(extra_citizens))]
        db.add(M.CollectionRequest(user_id=u.id, household_id=hh_by_user[u.id].id, ward_id=w.id, kind="household", stream=stream, material_key=mk_, status="requested", est_weight_kg=round(rng.uniform(1.5, 6), 1),
                                   lat=_jit(rng, w.lat), lng=_jit(rng, w.lng), scheduled_for=t0 + timedelta(days=1), data_class=SIM))
    # ---- complaints (clusters = repeated hotspots)
    clusters = [("Kodungaiyur", 5, "garbage_accumulation"), ("Velachery", 4, "overflowing_bin"), ("T. Nagar", 3, "illegal_dumping")]
    cats = list(cmp.CATS.keys())
    statuses = ["verified", "assigned", "in_progress", "resolution_submitted", "closed", "closed", "submitted", "reopened"]
    n = 0
    for wn, cnt, cat in clusters:
        w = wards[wn]
        clat, clng = w.lat + rng.uniform(-0.003, 0.003), w.lng + rng.uniform(-0.003, 0.003)
        for i in range(cnt):
            n += 1
            ago = rng.randint(1, 25)
            ts = t0 - timedelta(days=ago, hours=rng.randint(0, 20))
            u = extra_citizens[n % len(extra_citizens)]
            st = statuses[n % len(statuses)]
            c = M.Complaint(user_id=u.id, ward_id=w.id, category=cat, description=f"{cat.replace('_', ' ').title()} near {wn} (seeded demo report)", source="text", lat=clat + rng.uniform(-0.0006, 0.0006),
                            lng=clng + rng.uniform(-0.0006, 0.0006), status="submitted", priority=1 if i >= 2 else 2, repeat_count=cnt if i == 0 else 1, classification={"category": cat}, data_class=SIM, created_at=ts, updated_at=ts)
            db.add(c)
            db.flush()
            cmp.push_history(c, "submitted", u.name, "Report submitted")
            cmp.push_history(c, "verified", "Verification Agent", "Automated checks passed")
            if st not in ("submitted", "verified"):
                cmp.push_history(c, "assigned", "Meenakshi V. (demo ward officer)", "Assigned to ward sanitation team")
            if st in ("resolution_submitted", "closed"):
                cmp.push_history(c, "resolution_submitted", "Ward team", "Cleared and sanitised", evidence="photo ref (seeded)")
            if st == "closed":
                cmp.push_history(c, "closed", u.name, "Citizen confirmed resolution")
            if st == "in_progress":
                cmp.push_history(c, "in_progress", "Ward team", "Work started")
            if st == "reopened":
                cmp.push_history(c, "reopened", u.name, "Waste returned within 2 days")
            c.status = st
            c.created_at = ts
    for i in range(14):
        w = rng.choice(list(wards.values()))
        cat = rng.choice(cats)
        u = extra_citizens[i % len(extra_citizens)]
        ts = t0 - timedelta(days=rng.randint(1, 28))
        c = M.Complaint(user_id=u.id, ward_id=w.id, category=cat, description=f"{cat.replace('_', ' ').title()} in {w.name} (seeded demo report)", source=rng.choice(["text", "image", "voice"]),
                        lat=_jit(rng, w.lat, 0.012), lng=_jit(rng, w.lng, 0.012), status="submitted", priority=2, classification={"category": cat}, data_class=SIM, created_at=ts, updated_at=ts)
        db.add(c)
        db.flush()
        cmp.push_history(c, "submitted", u.name, "Report submitted")
        st = rng.choice(["submitted", "verified", "assigned", "closed", "closed", "in_progress"])
        if st != "submitted":
            cmp.push_history(c, "verified", "Verification Agent", "Automated checks passed")
        if st in ("assigned", "closed", "in_progress"):
            cmp.push_history(c, "assigned", "Meenakshi V. (demo ward officer)", "Assigned")
        if st == "closed":
            cmp.push_history(c, "resolution_submitted", "Ward team", "Cleared", evidence="photo ref (seeded)")
            cmp.push_history(c, "closed", u.name, "Citizen confirmed")
        c.status = st
    db.commit()
    # ---- events
    org = users["organiser@vyarthx.demo"]
    gu = wards["Guindy"]

    def event(name, venue, days_ahead, att, cat, food, status, vol, sponsor):
        e = M.Event(organiser_id=org.id, name=name, venue=venue, lat=gu.lat + rng.uniform(-0.004, 0.004), lng=gu.lng + rng.uniform(-0.004, 0.004), ward_id=gu.id, category=cat,
                    starts_at=t0 + timedelta(days=days_ahead), duration_h=6, expected_attendance=att, food=food, volunteers_available=vol, sponsor_requirements=sponsor, status=status, data_class=SIM)
        db.add(e)
        db.flush()
        e.plan = evs.plan_event(db, e)
        return e

    past = event("Campus Green Fest (completed demo)", "Demo College of Engineering, Guindy", -9, 420, "college", "stalls", "completed", 30, "Branding on segregation signage")
    past.actual_attendance = 398
    vol_users = extra_citizens[:6]
    db.add(M.EventParticipation(event_id=past.id, user_id=org.id, role="organiser", status="approved"))
    for u in vol_users:
        db.add(M.EventParticipation(event_id=past.id, user_id=u.id, role="volunteer", status="checked_in", hours=4))
    db.add(M.EventParticipation(event_id=past.id, user_id=users["recycler@vyarthx.demo"].id, role="recycler", org_name="Demo Recycler – Manali", status="approved"))
    db.add(M.EventParticipation(event_id=past.id, user_id=users["worker@vyarthx.demo"].id, role="collection_partner", org_name="Demo collection cooperative", status="approved"))
    db.add(M.EventParticipation(event_id=past.id, user_id=c1.id, role="sponsor", org_name="Demo eco-store (simulated sponsor)", contribution_inr=15000, status="approved"))
    for stream, kg, rec, ver, dest in [("wet", 118, True, True, "Demo Windrow Compost Plant – Velachery"), ("dry_recyclable", 142, True, True, "Demo Recycler – Manali"), ("reject", 39, False, True, "Residual — Perungudi dumpsite"),
                                       ("reusable", 12, True, True, "Demo Community NGO – Mylapore"), ("special", 1.5, False, True, "Special-care collection point")]:
        db.add(M.EventWaste(event_id=past.id, stream=stream, kg=kg, destination=dest, recovered=rec, verified=ver, logged_by=users["worker@vyarthx.demo"].id))
    db.flush()
    past.report = evs.build_report(db, past)
    if past.report["certificate_eligible"]:
        past.certificate = {"id": f"VX-ZW-{past.id:04d}", "issued_at": (t0 - timedelta(days=8)).isoformat(), "level": "Zero-Waste Event — verified diversion",
                            "verified_diversion_pct": round(100 * past.report["totals"]["diversion_verified"], 1), "basis": "Partner-verified quantities only", "data_class": SIM}
    e2 = event("Pongal Community Mela (demo)", "Besant Nagar community ground", 12, 800, "festival", "stalls", "planned", 20, "Seeking sponsors for segregation signage and compost bins")
    e2.ward_id, e2.lat, e2.lng = wards["Besant Nagar"].id, wards["Besant Nagar"].lat, wards["Besant Nagar"].lng
    db.add(M.EventParticipation(event_id=e2.id, user_id=org.id, role="organiser", status="approved"))
    db.add(M.EventParticipation(event_id=e2.id, user_id=extra_citizens[0].id, role="volunteer", status="registered", hours=0))
    e3 = event("Zero-Waste Wedding Showcase (demo)", "Demo convention hall, Mylapore", 25, 350, "wedding", "catered", "planned", 8, "Reusable decor sponsor")
    e3.ward_id, e3.lat, e3.lng = wards["Mylapore"].id, wards["Mylapore"].lat, wards["Mylapore"].lng
    db.add(M.EventParticipation(event_id=e3.id, user_id=org.id, role="organiser", status="approved"))
    db.commit()
    # ---- reuse listings
    reuse = [(users["organiser@vyarthx.demo"], "40 used hostel chairs", "furniture", "donate", 40, "Sturdy plastic-and-steel chairs, good condition", "Guindy"),
             (c1, "Wooden study table", "furniture", "giveaway", 1, "Minor scratches", "Adyar"), (users["citizen2@vyarthx.demo"], "School textbooks (Class 8-10)", "books", "donate", 25, "Good condition", "Anna Nagar"),
             (extra_citizens[1], "Old 32-inch monitor — not working", "electronics", "repair", 1, "Does not power on; needs repair assessment", "Velachery"),
             (extra_citizens[2], "Glass jars (clean)", "containers", "exchange", 30, "Clean, with lids", "T. Nagar"), (extra_citizens[3], "Leftover floor tiles", "construction", "sell", 60, "Unused, boxed", "Perungudi")]
    for u, title, cat, mode, qty, desc, wn in reuse:
        w = wards[wn]
        r = M.ReuseListing(user_id=u.id, title=title, category=cat, mode=mode, quantity=qty, description=desc, ward_id=w.id, lat=_jit(rng, w.lat), lng=_jit(rng, w.lng), condition="needs_repair" if "not working" in desc else "good",
                           price_inr=1200.0 if mode == "sell" else None, data_class=SIM)
        db.add(r)
        db.flush()
        cls = circular.classify_reuse(title, desc)
        r.ai = {"classification": cls, "recipients": circular.match_recipients(db, r), "ideas": circular.upcycling(cat)}
    # ---- pending facility authorisation approval + notifications
    pend = facs["Demo E-waste Collection Centre – Anna Nagar (PENDING approval)"]
    db.flush()
    db.add(M.Approval(action="facility_authorisation", title=f"Authorise facility: {pend.name}", payload={"facility_id": pend.id}, required_role="municipal", status="pending", requested_by=users["facility@vyarthx.demo"].id))
    db.add(M.Notification(user_id=c1.id, kind="info", title="Welcome to VYARTHX", message="This is a demo with simulated data. Try the Waste Doctor to start."))
    db.commit()
    return {"wards": len(wards), "facilities": len(facs) + 2, "users": len(PEOPLE) + len(extra_citizens) + 4}


def seed_activity(db: Session) -> None:
    """Populate the Agent Activity Centre by running real workflows through the orchestrator."""
    from ..services import demo_story

    demo_story.run_story(db, label="Seeded sample", quick=True)


def seed_if_empty(db: Session) -> bool:
    if db.scalar(select(func.count()).select_from(M.User)):
        return False
    seed_all(db)
    seed_activity(db)
    return True
