"""SQLAlchemy models — mirrors Doc 02 §3 data model exactly.

Invariants preserved:
- account stored only as KMS-keyed HMAC (account_hash + hash_version), never cleartext
- audit_logs hash-chained append-only (prev_hash / row_hash)
- report_votes per-user PK (anti double-vote)
- identity_trust starts at 10 (ADR-014)
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.enums import (
    AdminVerificationStatus,
    ApiKeyTier,
    BadgeType,
    BankType,
    DisputeStatus,
    EntityVerificationStatus,
    ProcessingStatus,
    ReportCategory,
    ReportStatus,
    ReviewFlagReason,
    ReviewFlagStatus,
    Role,
    UserStatus,
)

GEN_UUID = dict(default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    password_hash: Mapped[str | None] = mapped_column(Text)  # argon2id
    role: Mapped[str] = mapped_column(String(20), default=Role.USER, nullable=False)
    # identity-graph trust (ADR-014): NEW accounts start LOW (10), not 50
    identity_trust: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    reputation_score: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "role IN ('USER','ANALYST','SENIOR_ANALYST','SUPERADMIN')", name="ck_users_role"
        ),
        CheckConstraint(
            "status IN ('ACTIVE','WARNED','SUSPENDED','BANNED')", name="ck_users_status"
        ),
        CheckConstraint("identity_trust >= 0", name="ck_users_identity_trust_nonneg"),
    )


class PaymentEntity(Base):
    __tablename__ = "payment_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scheme: Mapped[str | None] = mapped_column(String(30))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    institution_code: Mapped[str | None] = mapped_column(String(50))
    # KMS-keyed HMAC-SHA256 canonical key (ADR-002/013) — index only, never reverse
    account_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    hash_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    account_masked: Mapped[str] = mapped_column(String(50), nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(150))
    merchant_city: Mapped[str | None] = mapped_column(String(100))
    # ADR-016 contextual name disclosure
    holder_name: Mapped[str | None] = mapped_column(String(150))
    holder_name_source: Mapped[str | None] = mapped_column(String(30))
    mcc: Mapped[str | None] = mapped_column(String(4))
    nmid: Mapped[str | None] = mapped_column(String(100))
    emvco_payload: Mapped[str | None] = mapped_column(Text)
    risk_score: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    verification_status: Mapped[str] = mapped_column(
        String(30), default=EntityVerificationStatus.UNVERIFIED, nullable=False
    )
    is_gov_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gov_source: Mapped[str | None] = mapped_column(String(100))  # attribution when gov-listed
    anomaly_spike_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dampen_factor: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), default=Decimal("1.00"), nullable=False
    )
    risk_factors: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    is_owner_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_reports: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_loss_reported: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0"), nullable=False
    )
    # per-currency map (Doc 02 §10.2): {"IDR": 7450000, "MYR": 3200}
    total_loss_by_currency: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    is_under_dispute: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dispute_hold_score_cap: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    owner_claimed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    owner_response: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('BANK_ACCOUNT','QR_CODE','E_WALLET','PHONE_ALIAS')",
            name="ck_entities_entity_type",
        ),
        CheckConstraint(
            "verification_status IN ('UNVERIFIED','COMMUNITY_REPORTED',"
            "'ADMIN_CONFIRMED_FRAUD','VERIFIED_LEGIT_OWNER','GOV_BLACKLISTED')",
            name="ck_entities_verification_status",
        ),
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_entities_risk_score"),
        CheckConstraint(
            "holder_name_source IS NULL OR holder_name_source IN"
            " ('OWNER_KYC_PROOF','COMMUNITY_REPORTED')",
            name="ck_entities_holder_name_source",
        ),
        Index("ix_entities_country_scheme", "country_code", "scheme"),
        Index("ix_entities_verification_status", "verification_status"),
    )


class EntitySearchStat(Base):
    __tablename__ = "entity_search_stats"

    payment_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_entities.id", ondelete="CASCADE"), primary_key=True
    )
    total_searches: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    searches_7d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    searches_30d: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_searched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_7d_window_started_at: Mapped[date | None] = mapped_column(Date)
    last_30d_window_started_at: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SearchEventDaily(Base):
    __tablename__ = "search_events_daily"

    payment_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_entities.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    search_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class FraudReport(Base):
    __tablename__ = "fraud_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    payment_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_entities.id", ondelete="CASCADE"), nullable=False
    )
    reporter_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    loss_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    incident_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)  # NULL once tombstoned (docs/10)
    processing_status: Mapped[str] = mapped_column(
        String(30), default=ProcessingStatus.PROCESSING, nullable=False
    )
    ai_risk_score: Mapped[int | None] = mapped_column(Integer)
    ai_forensic_notes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    admin_verification_status: Mapped[str] = mapped_column(
        String(30), default=AdminVerificationStatus.PENDING, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default=ReportStatus.ACTIVE, nullable=False)
    police_report_number: Mapped[str | None] = mapped_column(String(64))
    is_legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    upvotes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    downvotes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flags_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # tombstone marker
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            f"category IN ({','.join(repr(c.value) for c in ReportCategory)})",
            name="ck_reports_category",
        ),
        CheckConstraint("severity BETWEEN 1 AND 5", name="ck_reports_severity"),
        CheckConstraint(
            "processing_status IN ('PROCESSING','PUBLISHED','FAILED')",
            name="ck_reports_processing_status",
        ),
        CheckConstraint(
            "admin_verification_status IN ('PENDING','APPROVED','REJECTED')",
            name="ck_reports_admin_status",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','HIDDEN','REMOVED_BY_DISPUTE','REMOVED_BY_MODERATOR',"
            "'RESOLVED_BY_SETTLEMENT')",
            name="ck_reports_status",
        ),
        Index("ix_reports_entity_id", "payment_entity_id"),
    )


class ReportEvidence(Base):
    __tablename__ = "report_evidences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fraud_reports.id", ondelete="CASCADE"), nullable=False
    )
    media_url: Mapped[str] = mapped_column(Text, nullable=False)  # public REDACTED URL only
    original_quarantine_url: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_blurred_pii: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    image_hash: Mapped[str | None] = mapped_column(String(64))  # pHash dup detection
    ocr_extracted_text: Mapped[str | None] = mapped_column(Text)
    ai_tampering_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tampering_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "media_type IN ('TRANSFER_SLIP','CHAT_LOG','QR_IMAGE','OTHER')",
            name="ck_evidence_media_type",
        ),
    )


class OwnerDispute(Base):
    __tablename__ = "owner_disputes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    payment_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_entities.id", ondelete="CASCADE"), nullable=False
    )
    target_report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fraud_reports.id")
    )
    claimed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    claim_stage: Mapped[str] = mapped_column(
        String(30), default=DisputeStatus.UNCLAIMED, nullable=False
    )
    owner_proof_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_proof_document_url: Mapped[str] = mapped_column(Text, nullable=False)
    # two-step flow (ADR-004): dispute fields nullable until ownership proven
    dispute_reason: Mapped[str | None] = mapped_column(String(50))
    justification_statement: Mapped[str | None] = mapped_column(Text)
    counter_evidence_urls: Mapped[list[Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default=DisputeStatus.SUBMITTED, nullable=False)
    dispute_badge_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            f"status IN ({','.join(repr(s.value) for s in DisputeStatus)})",
            name="ck_disputes_status",
        ),
        CheckConstraint(
            f"claim_stage IN ({','.join(repr(s.value) for s in DisputeStatus)})",
            name="ck_disputes_claim_stage",
        ),
    )


class ReviewFlag(Base):
    __tablename__ = "review_flags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fraud_reports.id", ondelete="CASCADE"), nullable=False
    )
    flagged_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(30), default=ReviewFlagStatus.PENDING, nullable=False
    )
    reviewed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            f"reason IN ({','.join(repr(r.value) for r in ReviewFlagReason)})",
            name="ck_flags_reason",
        ),
        CheckConstraint("status IN ('PENDING','UPHELD','DISMISSED')", name="ck_flags_status"),
        # no duplicate flags per user per reason
        UniqueConstraint(
            "report_id", "flagged_by_user_id", "reason", name="uq_flag_report_user_reason"
        ),
    )


class ReportVote(Base):
    __tablename__ = "report_votes"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fraud_reports.id", ondelete="CASCADE"), primary_key=True
    )
    voter_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    vote: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("vote IN (-1, 1)", name="ck_votes_vote"),
        PrimaryKeyConstraint("report_id", "voter_user_id", name="pk_report_votes"),
    )


class AuditLog(Base):
    """Hash-chained append-only audit trail (tamper-evident, C-A4 / ADR-013)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_type: Mapped[str | None] = mapped_column(String(30))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)
    prev_hash: Mapped[str | None] = mapped_column(String(64))  # SHA256 of previous row
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_audit_logs_subject", "subject_type", "subject_id"),)


class Bank(Base):
    """Reference directory of SEA banks / e-wallets (Phase 1.1).

    Single source of truth for the reporting UI: a report's institution MUST be
    selected from this table, never free text. Seeded from
    ``app/data/banks/*.json`` via ``python -m app.seeds.seed_banks`` (G-8:
    demo-grade data, licensing review pending for production).
    """

    __tablename__ = "banks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # local bank code / token
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    bic: Mapped[str | None] = mapped_column(String(11))  # SWIFT/BIC, when published
    national_id: Mapped[str | None] = mapped_column(String(30))  # e.g. VN NAPAS BIN, SG GIRO code
    bank_type: Mapped[str] = mapped_column(String(20), nullable=False)
    min_length: Mapped[int | None] = mapped_column(Integer)
    max_length: Mapped[int | None] = mapped_column(Integer)
    aliases: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("country_code", "code", name="uq_banks_country_code"),
        CheckConstraint(
            f"bank_type IN ({','.join(repr(t.value) for t in BankType)})",
            name="ck_banks_bank_type",
        ),
        Index("ix_banks_country_code", "country_code"),
    )


class UserBadge(Base):
    """Community badges (Phase 3B): verified reporter, pioneer warn, scam-aware."""

    __tablename__ = "user_badges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    badge: Mapped[str] = mapped_column(String(40), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), default="", nullable=False)  # e.g. entity id
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "badge", "scope", name="uq_user_badges"),
        CheckConstraint(
            f"badge IN ({','.join(repr(b.value) for b in BadgeType)})",
            name="ck_user_badges_badge",
        ),
        Index("ix_user_badges_user", "user_id"),
    )


class WatchlistEntry(Base):
    """Saved entities a user follows for report/band/dispute/gov alerts (Phase 3B.4)."""

    __tablename__ = "watchlist_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    payment_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_entities.id", ondelete="CASCADE"), nullable=False
    )
    notify_reports: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_band: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "payment_entity_id", name="uq_watchlist_user_entity"),
        Index("ix_watchlist_user", "user_id"),
        Index("ix_watchlist_entity", "payment_entity_id"),
    )


class AdminApproval(Base):
    """Four-eyes dual-control queue for destructive/trust-altering admin actions (Phase 6.5)."""

    __tablename__ = "admin_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','CANCELLED')", name="ck_admin_approvals_status"
        ),
        Index("ix_admin_approvals_status", "status"),
    )


class ApiKey(Base):
    """Public screen-API key (Phase 9 / docs/09). Raw key is shown once; only the
    SHA-256 hash + last-4 are stored."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), default="default", nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default=ApiKeyTier.DEMO, nullable=False)
    scopes: Mapped[list[Any]] = mapped_column(
        JSONB, default=lambda: ["screen:read"], nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            f"tier IN ({','.join(repr(t.value) for t in ApiKeyTier)})", name="ck_api_keys_tier"
        ),
        Index("ix_api_keys_user", "user_id"),
    )


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, **GEN_UUID)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)
