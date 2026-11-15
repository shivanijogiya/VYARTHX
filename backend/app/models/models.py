"""VYARTHX shared data model. Every record carries a `data_class`:
official | pilot | estimate | simulated  (see docs/DATA_SOURCES.md)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database.db import Base


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def pk() -> Mapped[int]:
    return mapped_column(Integer, primary_key=True, autoincrement=True)


class Ward(Base):
    __tablename__ = "wards"
    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(80), unique=True)
    zone: Mapped[str] = mapped_column(String(60), default="")
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    population: Mapped[int] = mapped_column(Integer, default=0)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    source_note: Mapped[str] = mapped_column(String(300), default="")


class WardDaily(Base):
    """Simulated daily city baseline per ward (tonnes). Never presented as official."""
    __tablename__ = "ward_daily"
    id: Mapped[int] = pk()
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"), index=True)
    day: Mapped[datetime] = mapped_column(DateTime, index=True)
    generated_t: Mapped[float] = mapped_column(Float)
    collected_t: Mapped[float] = mapped_column(Float)
    segregated_t: Mapped[float] = mapped_column(Float)
    processed_t: Mapped[float] = mapped_column(Float)
    recovered_t: Mapped[float] = mapped_column(Float)
    residual_t: Mapped[float] = mapped_column(Float)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = pk()
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30), index=True)  # citizen|worker|municipal|facility|organiser|recycler
    password_hash: Mapped[str] = mapped_column(String(300))
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    community_id: Mapped[Optional[int]] = mapped_column(ForeignKey("communities.id"), nullable=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    prefs: Mapped[dict] = mapped_column(JSON, default=dict)  # notification prefs, goals, privacy
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ward = relationship("Ward")


class Household(Base):
    __tablename__ = "households"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)  # printed QR payload
    address: Mapped[str] = mapped_column(String(200), default="")
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")


class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    worker_code: Mapped[str] = mapped_column(String(30), unique=True)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    identity_status: Mapped[str] = mapped_column(String(30), default="optional_unverified")
    onboarding_partner: Mapped[str] = mapped_column(String(120), default="")
    lat: Mapped[float] = mapped_column(Float, default=0)
    lng: Mapped[float] = mapped_column(Float, default=0)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    capacity_kg: Mapped[float] = mapped_column(Float, default=150)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    training: Mapped[list] = mapped_column(JSON, default=list)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")


class WorkerPayment(Base):
    """Simulated earnings ledger. No real money moves."""
    __tablename__ = "worker_payments"
    id: Mapped[int] = pk()
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.id"), index=True)
    collection_id: Mapped[Optional[int]] = mapped_column(ForeignKey("collection_requests.id"), nullable=True)
    amount_inr: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(30), default="recorded_simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("worker_id", "collection_id", name="uq_worker_collection_pay"),)


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(30), index=True)
    # mrf|recycler|compost|vermicompost|biomethanation|special_care|ewaste|landfill|dumpsite|ngo|refurbisher|school|nursery
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    capacity_tpd: Mapped[float] = mapped_column(Float, default=0)
    load_tpd: Mapped[float] = mapped_column(Float, default=0)
    accepts: Mapped[list] = mapped_column(JSON, default=list)  # material keys / streams
    authorised: Mapped[bool] = mapped_column(Boolean, default=False)
    authorisation_note: Mapped[str] = mapped_column(String(200), default="")
    downtime: Mapped[bool] = mapped_column(Boolean, default=False)
    remaining_capacity_t: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # landfill only
    reported_capacity_t: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity_class: Mapped[str] = mapped_column(String(20), default="simulated")
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    source_note: Mapped[str] = mapped_column(String(300), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = pk()
    code: Mapped[str] = mapped_column(String(30), unique=True)
    capacity_kg: Mapped[float] = mapped_column(Float, default=1500)
    ward_id: Mapped[int] = mapped_column(ForeignKey("wards.id"))
    status: Mapped[str] = mapped_column(String(20), default="available")  # available|on_route|maintenance
    lat: Mapped[float] = mapped_column(Float, default=0)
    lng: Mapped[float] = mapped_column(Float, default=0)
    gps_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    household_id: Mapped[Optional[int]] = mapped_column(ForeignKey("households.id"), nullable=True)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    image_path: Mapped[str] = mapped_column(String(300), default="")
    sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    phash: Mapped[str] = mapped_column(String(32), default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    client_ts: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    detected_object: Mapped[str] = mapped_column(String(120), default="")
    material: Mapped[str] = mapped_column(String(80), default="")
    material_key: Mapped[str] = mapped_column(String(40), default="")
    stream: Mapped[str] = mapped_column(String(20), default="")  # wet|dry|sanitary|special|undetermined
    confidence: Mapped[float] = mapped_column(Float, default=0)
    contamination: Mapped[str] = mapped_column(String(20), default="none")  # none|possible|detected
    est_weight_kg: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default="classified")
    # classified|needs_clarification|verified|flagged|scheduled|collected|completed
    classification: Mapped[dict] = mapped_column(JSON, default=dict)
    verification: Mapped[dict] = mapped_column(JSON, default=dict)
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class CollectionRequest(Base):
    __tablename__ = "collection_requests"
    id: Mapped[int] = pk()
    submission_id: Mapped[Optional[int]] = mapped_column(ForeignKey("submissions.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    household_id: Mapped[Optional[int]] = mapped_column(ForeignKey("households.id"), nullable=True)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workers.id"), nullable=True)
    suggested_worker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("workers.id"), nullable=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("batches.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="household")  # household|special|marketplace|event|ewaste
    stream: Mapped[str] = mapped_column(String(20), default="dry")
    material_key: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(30), default="requested", index=True)
    # requested|assigned|accepted|collected|delivered|completed|cancelled|rejected_by_worker
    priority: Mapped[int] = mapped_column(Integer, default=2)
    est_weight_kg: Mapped[float] = mapped_column(Float, default=0)
    verified_weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weight_source: Mapped[str] = mapped_column(String(40), default="")  # manual_entry|calibrated_scale
    lat: Mapped[float] = mapped_column(Float, default=0)
    lng: Mapped[float] = mapped_column(Float, default=0)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    qr_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str] = mapped_column(String(300), default="")
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Batch(Base):
    """Waste Passport batch."""
    __tablename__ = "batches"
    id: Mapped[int] = pk()
    code: Mapped[str] = mapped_column(String(30), unique=True)
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    parent_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("batches.id"), nullable=True)
    stream: Mapped[str] = mapped_column(String(20), default="dry")
    material: Mapped[str] = mapped_column(String(80), default="")
    material_key: Mapped[str] = mapped_column(String(40), default="")
    input_kg: Mapped[float] = mapped_column(Float, default=0)
    recovered_kg: Mapped[float] = mapped_column(Float, default=0)
    rejects_kg: Mapped[float] = mapped_column(Float, default=0)
    loss_kg: Mapped[float] = mapped_column(Float, default=0)
    other_kg: Mapped[float] = mapped_column(Float, default=0)
    residual_kg: Mapped[float] = mapped_column(Float, default=0)
    residual_destination: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(40), default="at_household")
    # at_household|collected|at_facility|processing|recovery_completed|partially_recovered|residual_recorded
    current_facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PassportEvent(Base):
    """Append-only, hash-chained traceability event."""
    __tablename__ = "passport_events"
    id: Mapped[int] = pk()
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(30))  # household|collector|mrf|recycler|residual|final
    event_type: Mapped[str] = mapped_column(String(60))
    actor_name: Mapped[str] = mapped_column(String(120), default="")
    actor_role: Mapped[str] = mapped_column(String(30), default="")
    location: Mapped[str] = mapped_column(String(200), default="")
    weight_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="recorded")  # recorded|verified|flagged
    evidence: Mapped[str] = mapped_column(String(300), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    ts: Mapped[datetime] = mapped_column(DateTime, default=now)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), default="")
    __table_args__ = (UniqueConstraint("batch_id", "seq", name="uq_batch_seq"),)


class ProcessingRecord(Base):
    __tablename__ = "processing_records"
    id: Mapped[int] = pk()
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    process: Mapped[str] = mapped_column(String(40), default="sorting")
    input_kg: Mapped[float] = mapped_column(Float, default=0)
    recovered_kg: Mapped[float] = mapped_column(Float, default=0)
    rejects_kg: Mapped[float] = mapped_column(Float, default=0)
    loss_kg: Mapped[float] = mapped_column(Float, default=0)
    other_kg: Mapped[float] = mapped_column(Float, default=0)
    residual_kg: Mapped[float] = mapped_column(Float, default=0)
    output_estimate: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g. compost kg (estimate)
    confirmed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RewardTransaction(Base):
    """Append-only GreenPoints ledger. Balances are always derived from this table."""
    __tablename__ = "reward_transactions"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    bucket: Mapped[str] = mapped_column(String(20))  # provisional|verified|final
    amount: Mapped[int] = mapped_column(Integer)  # signed
    kind: Mapped[str] = mapped_column(String(40))
    ref_type: Mapped[str] = mapped_column(String(30), default="")
    ref_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    idem_key: Mapped[str] = mapped_column(String(120), unique=True)
    note: Mapped[str] = mapped_column(String(300), default="")
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class RewardCatalog(Base):
    __tablename__ = "reward_catalog"
    id: Mapped[int] = pk()
    partner: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))  # transport|rail|municipal|local|community|education
    scope: Mapped[str] = mapped_column(String(20), default="partner")  # partner|community
    points_cost: Mapped[int] = mapped_column(Integer)
    eligibility: Mapped[str] = mapped_column(String(300), default="")
    integration_status: Mapped[str] = mapped_column(String(200), default="")
    simulation_only: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    min_level: Mapped[int] = mapped_column(Integer, default=0)


class Redemption(Base):
    __tablename__ = "redemptions"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    catalog_id: Mapped[int] = mapped_column(ForeignKey("reward_catalog.id"))
    points: Mapped[int] = mapped_column(Integer)
    voucher_code: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default="issued_demo_voucher")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    catalog = relationship("RewardCatalog")


class MarketListing(Base):
    __tablename__ = "market_listings"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(10))  # supply|demand
    material_key: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    quantity_kg: Mapped[float] = mapped_column(Float)
    remaining_kg: Mapped[float] = mapped_column(Float, default=0)
    condition: Mapped[str] = mapped_column(String(60), default="clean")
    contamination: Mapped[str] = mapped_column(String(20), default="none")
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    pickup_window: Mapped[str] = mapped_column(String(80), default="")
    price_inr_per_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_source: Mapped[str] = mapped_column(String(160), default="user-entered, indicative only")
    seller_type: Mapped[str] = mapped_column(String(40), default="household")
    verification: Mapped[str] = mapped_column(String(30), default="unverified")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|matched|closed
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class MarketMatch(Base):
    __tablename__ = "market_matches"
    id: Mapped[int] = pk()
    supply_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"))
    demand_id: Mapped[int] = mapped_column(ForeignKey("market_listings.id"))
    qty_kg: Mapped[float] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="recommended")
    # recommended|requested|accepted|rejected|completed
    rationale: Mapped[dict] = mapped_column(JSON, default=dict)
    collection_id: Mapped[Optional[int]] = mapped_column(ForeignKey("collection_requests.id"), nullable=True)
    requested_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("supply_id", "demand_id", name="uq_match_pair"),)


class ReuseListing(Base):
    __tablename__ = "reuse_listings"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(20))  # sell|donate|exchange|giveaway|repair
    condition: Mapped[str] = mapped_column(String(40), default="good")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    lat: Mapped[float] = mapped_column(Float, default=0)
    lng: Mapped[float] = mapped_column(Float, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    price_inr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|matched|transferred
    ai: Mapped[dict] = mapped_column(JSON, default=dict)  # category/condition guess, matches, upcycling ideas
    recipient: Mapped[str] = mapped_column(String(160), default="")
    transferred_qty: Mapped[int] = mapped_column(Integer, default=0)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Complaint(Base):
    __tablename__ = "complaints"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="garbage_accumulation")
    description: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="text")  # text|image|voice
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    image_path: Mapped[str] = mapped_column(String(300), default="")
    phash: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(30), default="submitted", index=True)
    # submitted|ai_classified|verified|assigned|in_progress|resolution_submitted|closed|reopened
    priority: Mapped[int] = mapped_column(Integer, default=2)
    duplicate_of: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    repeat_count: Mapped[int] = mapped_column(Integer, default=1)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    resolution_evidence: Mapped[str] = mapped_column(String(300), default="")
    classification: Mapped[dict] = mapped_column(JSON, default=dict)
    history: Mapped[list] = mapped_column(JSON, default=list)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Community(Base):
    __tablename__ = "communities"
    id: Mapped[int] = pk()
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(20))  # apartment|college|office|ward|school
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    members_base: Mapped[int] = mapped_column(Integer, default=100)
    base_seg_rate: Mapped[float] = mapped_column(Float, default=0.6)
    base_participation: Mapped[float] = mapped_column(Float, default=0.5)
    base_contamination: Mapped[float] = mapped_column(Float, default=0.2)
    base_handover: Mapped[float] = mapped_column(Float, default=0.7)
    base_points: Mapped[int] = mapped_column(Integer, default=0)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")


class Challenge(Base):
    __tablename__ = "challenges"
    id: Mapped[int] = pk()
    community_id: Mapped[Optional[int]] = mapped_column(ForeignKey("communities.id"), nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(160))
    cadence: Mapped[str] = mapped_column(String(20), default="weekly")  # weekly|monthly
    description: Mapped[str] = mapped_column(Text, default="")
    rule: Mapped[str] = mapped_column(String(40), default="verified_submissions")  # verified_submissions|clean_streak|ewaste|reuse|compost
    target: Mapped[int] = mapped_column(Integer, default=5)
    points_reward: Mapped[int] = mapped_column(Integer, default=25)
    starts_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    ends_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    status: Mapped[str] = mapped_column(String(20), default="active")
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")


class ChallengeParticipation(Base):
    __tablename__ = "challenge_participation"
    id: Mapped[int] = pk()
    challenge_id: Mapped[int] = mapped_column(ForeignKey("challenges.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("challenge_id", "user_id", name="uq_chal_user"),)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = pk()
    organiser_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    venue: Mapped[str] = mapped_column(String(200), default="")
    lat: Mapped[float] = mapped_column(Float, default=0)
    lng: Mapped[float] = mapped_column(Float, default=0)
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(40), default="college")
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    duration_h: Mapped[float] = mapped_column(Float, default=4)
    expected_attendance: Mapped[int] = mapped_column(Integer, default=100)
    actual_attendance: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    food: Mapped[str] = mapped_column(String(30), default="none")  # none|packaged|catered|stalls
    volunteers_available: Mapped[int] = mapped_column(Integer, default=0)
    sponsor_requirements: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned|live|completed
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    certificate: Mapped[dict] = mapped_column(JSON, default=dict)
    data_class: Mapped[str] = mapped_column(String(20), default="simulated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class EventParticipation(Base):
    __tablename__ = "event_participation"
    id: Mapped[int] = pk()
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(30))
    # volunteer|sponsor|collection_partner|recycler|attendee|audience|municipal
    org_name: Mapped[str] = mapped_column(String(160), default="")
    contribution_inr: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="registered")  # registered|pending|approved|checked_in
    hours: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("event_id", "user_id", "role", name="uq_event_user_role"),)


class EventWaste(Base):
    __tablename__ = "event_waste"
    id: Mapped[int] = pk()
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    stream: Mapped[str] = mapped_column(String(30))  # wet|dry_recyclable|reject|special|reusable
    kg: Mapped[float] = mapped_column(Float)
    destination: Mapped[str] = mapped_column(String(160), default="")
    recovered: Mapped[bool] = mapped_column(Boolean, default=False)  # sent for recovery (not disposal)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)  # confirmed by a partner/facility, not organiser
    logged_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class RoutePlan(Base):
    __tablename__ = "route_plans"
    id: Mapped[int] = pk()
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    facility_id: Mapped[Optional[int]] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    stops: Mapped[list] = mapped_column(JSON, default=list)
    distance_km: Mapped[float] = mapped_column(Float, default=0)
    load_kg: Mapped[float] = mapped_column(Float, default=0)
    est_fuel_l: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(30), default="proposed")  # proposed|approved_simulated|rejected
    solver: Mapped[str] = mapped_column(String(40), default="ortools")
    distance_basis: Mapped[str] = mapped_column(String(80), default="haversine x1.3")
    plan_group: Mapped[str] = mapped_column(String(40), default="")
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    id: Mapped[int] = pk()
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = pk()
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="info")
    title: Mapped[str] = mapped_column(String(160), default="")
    message: Mapped[str] = mapped_column(String(400), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ConfigEntry(Base):
    __tablename__ = "config_entries"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = pk()
    workflow: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(30), default="running")
    # running|completed|awaiting_approval|failed|rejected|escalated
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    mode: Mapped[str] = mapped_column(String(30), default="deterministic")  # deterministic|llm_assisted
    summary: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    steps = relationship("AgentStep", back_populates="run", order_by="AgentStep.seq")


class AgentStep(Base):
    __tablename__ = "agent_steps"
    id: Mapped[int] = pk()
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(60))
    actor_type: Mapped[str] = mapped_column(String(20), default="agent")  # agent|human|service|orchestrator
    task: Mapped[str] = mapped_column(String(300), default="")
    tool: Mapped[str] = mapped_column(String(80), default="")
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|success|failed|retried|skipped|escalated
    approval_status: Mapped[str] = mapped_column(String(20), default="not_required")  # not_required|pending|approved|rejected
    next_agent: Mapped[str] = mapped_column(String(60), default="")
    retries: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(400), default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    run = relationship("AgentRun", back_populates="steps")


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = pk()
    run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agent_runs.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))  # route_dispatch|marketplace_pickup|facility_authorisation|complaint_closure|...
    title: Mapped[str] = mapped_column(String(200), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    required_role: Mapped[str] = mapped_column(String(30), default="municipal")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    decided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decision_note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = pk()
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(60), default="")
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
