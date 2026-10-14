"""Canonical shared enums — single source of truth mirrored from Doc 02 §3/§4.3.

One category taxonomy shared by DB, NLP, and API (invariant: no second taxonomy).
"""

from enum import StrEnum


class Role(StrEnum):
    USER = "USER"
    ANALYST = "ANALYST"
    SENIOR_ANALYST = "SENIOR_ANALYST"
    SUPERADMIN = "SUPERADMIN"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    WARNED = "WARNED"
    SUSPENDED = "SUSPENDED"
    BANNED = "BANNED"


class EntityType(StrEnum):
    BANK_ACCOUNT = "BANK_ACCOUNT"
    QR_CODE = "QR_CODE"
    E_WALLET = "E_WALLET"
    PHONE_ALIAS = "PHONE_ALIAS"


class Scheme(StrEnum):
    QRIS = "QRIS"
    DUITNOW = "DUITNOW"
    PROMPTPAY = "PROMPTPAY"
    PAYNOW = "PAYNOW"
    VIETQR = "VIETQR"
    QRPH = "QRPH"
    BANK = "BANK"


class EntityVerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    COMMUNITY_REPORTED = "COMMUNITY_REPORTED"
    ADMIN_CONFIRMED_FRAUD = "ADMIN_CONFIRMED_FRAUD"
    VERIFIED_LEGIT_OWNER = "VERIFIED_LEGIT_OWNER"
    GOV_BLACKLISTED = "GOV_BLACKLISTED"


class HolderNameSource(StrEnum):
    OWNER_KYC_PROOF = "OWNER_KYC_PROOF"
    COMMUNITY_REPORTED = "COMMUNITY_REPORTED"


class ReportCategory(StrEnum):
    """The ONE canonical taxonomy (Doc 02 §3.3/§4.3)."""

    ONLINE_SHOP_GHOSTING = "ONLINE_SHOP_GHOSTING"
    FAKE_JOB = "FAKE_JOB"
    INVESTMENT_PIG_BUTCHERING = "INVESTMENT_PIG_BUTCHERING"
    PHISHING_PRETEXTING = "PHISHING_PRETEXTING"
    IMPERSONATION = "IMPERSONATION"
    UNAUTHORIZED_LENDING_PINJOL = "UNAUTHORIZED_LENDING_PINJOL"
    NO_DELIVERY_GOODS = "NO_DELIVERY_GOODS"
    EVENT_TICKET_FRAUD = "EVENT_TICKET_FRAUD"
    OTHER = "OTHER"


class ProcessingStatus(StrEnum):
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class AdminVerificationStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ReportStatus(StrEnum):
    ACTIVE = "ACTIVE"
    HIDDEN = "HIDDEN"
    REMOVED_BY_DISPUTE = "REMOVED_BY_DISPUTE"
    REMOVED_BY_MODERATOR = "REMOVED_BY_MODERATOR"
    RESOLVED_BY_SETTLEMENT = "RESOLVED_BY_SETTLEMENT"


class DisputeStatus(StrEnum):
    """Shared by owner_disputes.status and claim_stage (Doc 02 §3.5)."""

    UNCLAIMED = "UNCLAIMED"
    SUBMITTED = "SUBMITTED"
    AI_VERIFYING = "AI_VERIFYING"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED_REMOVED = "APPROVED_REMOVED"
    REJECTED_IDENTITY = "REJECTED_IDENTITY"
    REJECTED_UPHELD = "REJECTED_UPHELD"
    SETTLEMENT = "SETTLEMENT"


class OwnerProofType(StrEnum):
    BANK_PASSBOOK = "BANK_PASSBOOK"
    MBANKING_SCREENSHOT = "MBANKING_SCREENSHOT"
    MERCHANT_PORTAL_NMID = "MERCHANT_PORTAL_NMID"
    MICRO_DEPOSIT_OTP = "MICRO_DEPOSIT_OTP"


class DisputeReason(StrEnum):
    SPAM_REVIEW_BOMB = "SPAM_REVIEW_BOMB"
    RESOLVED_REFUNDED = "RESOLVED_REFUNDED"
    IDENTITY_THEFT = "IDENTITY_THEFT"
    FALSE_CLAIM = "FALSE_CLAIM"
    OTHER = "OTHER"


class ReviewFlagReason(StrEnum):
    DEFAMATION_SPAM = "DEFAMATION_SPAM"
    INCORRECT_ACCOUNT = "INCORRECT_ACCOUNT"
    OFFENSIVE_CONTENT = "OFFENSIVE_CONTENT"
    OTHER = "OTHER"


class ReviewFlagStatus(StrEnum):
    PENDING = "PENDING"
    UPHELD = "UPHELD"
    DISMISSED = "DISMISSED"


class EvidenceMediaType(StrEnum):
    TRANSFER_SLIP = "TRANSFER_SLIP"
    CHAT_LOG = "CHAT_LOG"
    QR_IMAGE = "QR_IMAGE"
    OTHER = "OTHER"


class RiskLevel(StrEnum):
    """Shared risk_level enum (Doc 02 §7.2 C9 fix)."""

    LOW_RISK = "LOW_RISK"  # 0-20
    CAUTION = "CAUTION"  # 21-50
    HIGH_RISK = "HIGH_RISK"  # 51-79
    CRITICAL_FRAUD = "CRITICAL_FRAUD"  # 80-100

    @classmethod
    def from_score(cls, score: int) -> "RiskLevel":
        if score <= 20:
            return cls.LOW_RISK
        if score <= 50:
            return cls.CAUTION
        if score <= 79:
            return cls.HIGH_RISK
        return cls.CRITICAL_FRAUD
