"""Green Neighbourhood League, challenges and behavioural intelligence tools. Rankings use verified quality — never kilograms."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.models import (Challenge, ChallengeParticipation, CollectionRequest, Community, Event, Submission, User, now)
from . import rewards
from .common import get_cfg

PRIOR_N = 20  # pseudo-observations carried by the (simulated) baseline


def community_stats(db: Session, c: Community, days: int = 30) -> dict:
    members = db.scalars(select(User).where(User.community_id == c.id)).all()
    ids = [m.id for m in members]
    since = now() - timedelta(days=days)
    subs = db.scalars(select(Submission).where(Submission.user_id.in_(ids), Submission.created_at >= since)).all() if ids else []
    n = len(subs)
    good = sum(1 for s in subs if s.status in ("verified", "scheduled", "collected", "completed") and s.contamination == "none")
    contam = sum(1 for s in subs if s.contamination in ("possible", "detected"))
    collected = sum(1 for s in subs if s.status in ("collected", "completed"))
    active = len({s.user_id for s in subs})
    seg = (c.base_seg_rate * PRIOR_N + good) / (PRIOR_N + n)
    cont = (c.base_contamination * PRIOR_N + contam) / (PRIOR_N + n)
    han = (c.base_handover * PRIOR_N + collected) / (PRIOR_N + n)
    part_live = (active / len(members)) if members else 0
    w = n / (PRIOR_N + n)
    part = c.base_participation * (1 - w) + part_live * w if members else c.base_participation
    pts = c.base_points + rewards.community_points(db, ids, days)
    score = 100 * (0.35 * seg + 0.25 * part + 0.20 * (1 - cont) + 0.20 * han)
    return {"id": c.id, "name": c.name, "type": c.type, "ward_id": c.ward_id, "members_registered": len(members), "members_estimated": c.members_base,
            "verified_segregation_pct": round(100 * seg, 1), "participation_pct": round(100 * part, 1), "contamination_pct": round(100 * cont, 1),
            "correct_handover_pct": round(100 * han, 1), "points": pts, "score": round(score, 1), "live_submissions": n,
            "data_class": c.data_class, "basis": "Baseline simulated values blended with live platform activity (20 pseudo-observations prior)"}


def leaderboard(db: Session, ctype: str | None = None, days: int = 30) -> list[dict]:
    q = select(Community)
    if ctype and ctype != "all":
        q = q.where(Community.type == ctype)
    rows = [community_stats(db, c, days) for c in db.scalars(q).all()]
    rows.sort(key=lambda r: -r["score"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def on_verified_event(db: Session, user_id: int, rule: str) -> list[dict]:
    """Advance challenge progress for a verified action; award completion bonus once (idempotent)."""
    done = []
    u = db.get(User, user_id)
    for ch in db.scalars(select(Challenge).where(Challenge.status == "active", Challenge.ends_at >= now(), Challenge.rule == rule)).all():
        if ch.community_id and (not u or u.community_id != ch.community_id):
            continue
        p = db.scalars(select(ChallengeParticipation).where(ChallengeParticipation.challenge_id == ch.id, ChallengeParticipation.user_id == user_id)).first()
        if not p or p.completed:
            continue
        p.progress += 1
        if p.progress >= ch.target:
            p.completed = True
            tx = rewards._add(db, user_id, "verified", ch.points_reward, "bonus", f"chal:{ch.id}:{user_id}", "challenge", ch.id, f"Challenge completed: {ch.title}")
            done.append({"challenge": ch.title, "points": ch.points_reward if tx else 0})
    return done


TIPS = {
    "en": {"wet": "Wet waste: kitchen and garden waste — keep it free of plastic.", "dry": "Dry waste: clean paper, plastic, metal and glass.",
           "sanitary": "Sanitary waste: wrap it and keep it separate.", "special": "Special-care waste: batteries, bulbs, medicines — authorised handover only."},
    "ta": {"wet": "ஈரக் கழிவு: சமையலறை மற்றும் தோட்டக் கழிவு — பிளாஸ்டிக் சேர்க்க வேண்டாம்.", "dry": "உலர் கழிவு: சுத்தமான காகிதம், பிளாஸ்டிக், உலோகம், கண்ணாடி.",
           "sanitary": "சுகாதாரக் கழிவு: சுற்றி தனியாக வைக்கவும்.", "special": "சிறப்புக் கவனக் கழிவு: பேட்டரி, பல்பு, மருந்து — அங்கீகரிக்கப்பட்ட சேகரிப்பில் மட்டும்."},
    "hi": {"wet": "गीला कचरा: रसोई और बगीचे का कचरा — प्लास्टिक न मिलाएँ।", "dry": "सूखा कचरा: साफ़ कागज़, प्लास्टिक, धातु, काँच।",
           "sanitary": "सैनिटरी कचरा: लपेटकर अलग रखें।", "special": "विशेष-देखभाल कचरा: बैटरी, बल्ब, दवाइयाँ — केवल अधिकृत संग्रह में दें।"},
}
TIPS_NOTE = "Local-language tips are machine-written drafts and should be reviewed by native speakers before real use."


def behaviour_profile(db: Session, user: User) -> dict:
    since = now() - timedelta(days=30)
    subs = db.scalars(select(Submission).where(Submission.user_id == user.id, Submission.created_at >= since).order_by(Submission.created_at.desc())).all()
    n = len(subs)
    clean = sum(1 for s in subs if s.contamination == "none" and s.status != "flagged")
    seg_score = round(100 * clean / n) if n else 0
    streak = rewards.streak_days(db, user.id)
    prefs = user.prefs or {}
    goals = prefs.get("goals", {"weekly_submissions": 3})
    wk = db.scalar(select(func.count()).select_from(Submission).where(Submission.user_id == user.id, Submission.created_at >= now() - timedelta(days=7))) or 0
    issues: dict[str, int] = {}
    for s in subs[:10]:
        if s.contamination in ("detected", "possible"):
            issues[s.material or "item"] = issues.get(s.material or "item", 0) + 1
    nudges = []
    if issues:
        top = max(issues.items(), key=lambda kv: kv[1])
        nudges.append({"type": "contamination", "title": f"Recurring contamination: {top[0]}", "body": "Several recent submissions looked soiled or mixed. Rinse containers lightly and separate food-soiled parts before handover — recyclers often reject soiled paper and plastic.",
                       "action": {"label": "Open Waste Doctor", "to": "/doctor"}})
    if streak >= 3:
        nudges.append({"type": "streak", "title": f"{streak}-day streak!", "body": "Consistent verified handovers earn a small behaviour bonus (capped).", "action": None})
    if wk < goals.get("weekly_submissions", 3):
        nudges.append({"type": "goal", "title": "Weekly goal in reach", "body": f"{wk} of {goals.get('weekly_submissions', 3)} verified-intent submissions this week.", "action": {"label": "Identify waste", "to": "/doctor"}})
    if user.community_id:
        c = db.get(Community, user.community_id)
        st = community_stats(db, c)
        if st["contamination_pct"] > 20:
            nudges.append({"type": "community", "title": "Community contamination is high", "body": f"{c.name} is at {st['contamination_pct']}% contamination. A Zero-Contamination Week challenge could help.", "action": {"label": "View challenges", "to": "/community"}})
    weekly = []
    for i in range(3, -1, -1):
        a, b = now() - timedelta(days=7 * (i + 1)), now() - timedelta(days=7 * i)
        ws = [s for s in subs if a <= s.created_at < b]
        weekly.append({"week": f"-{i}w" if i else "this week", "submissions": len(ws), "clean_pct": round(100 * sum(1 for s in ws if s.contamination == "none") / len(ws)) if ws else None})
    return {"segregation_score": seg_score, "streak_days": streak, "submissions_30d": n, "weekly_goal": goals, "this_week": wk, "progress": weekly,
            "issues": issues, "nudges": nudges, "tips": TIPS.get(user.language, TIPS["en"]), "tips_note": TIPS_NOTE if user.language != "en" else "",
            "notification_prefs": prefs.get("notifications", {"enabled": True, "max_per_day": 6, "reminders": True})}
