"""Canonical-enum invariants (Doc 02 §3.3/§4.3, ADR-017).

The ONE taxonomy must stay in sync with the DB CHECK constraints generated
from the shared StrEnum, and risk bands must match the C9 shared mapping.
"""

from app.enums import DisputeStatus, ReportCategory, RiskLevel
from app.models import FraudReport


def test_report_category_has_nine_members() -> None:
    assert len(ReportCategory) == 9
    assert "EVENT_TICKET_FRAUD" in {c.value for c in ReportCategory}


def test_db_check_generated_from_enum() -> None:
    """fraud_reports.category CHECK must list exactly the shared taxonomy."""
    checks = [
        c
        for c in FraudReport.__table__.constraints
        if getattr(c, "name", None) == "ck_reports_category"
    ]
    assert checks, "ck_reports_category missing — taxonomy not enforced at DB level"
    sqltext = str(checks[0].sqltext)
    for member in ReportCategory:
        assert member.value in sqltext


def test_dispute_status_shared_by_both_columns() -> None:
    """claim_stage and status reuse the SAME enum (Doc 02 §3.5 state-machine alignment)."""
    assert len(DisputeStatus) == 8
    for member in DisputeStatus:
        assert member.value in DisputeStatus.__members__


def test_risk_level_bands() -> None:
    assert RiskLevel.from_score(0) == RiskLevel.LOW_RISK
    assert RiskLevel.from_score(20) == RiskLevel.LOW_RISK
    assert RiskLevel.from_score(21) == RiskLevel.CAUTION
    assert RiskLevel.from_score(50) == RiskLevel.CAUTION
    assert RiskLevel.from_score(51) == RiskLevel.HIGH_RISK
    assert RiskLevel.from_score(79) == RiskLevel.HIGH_RISK
    assert RiskLevel.from_score(80) == RiskLevel.CRITICAL_FRAUD
    assert RiskLevel.from_score(100) == RiskLevel.CRITICAL_FRAUD
