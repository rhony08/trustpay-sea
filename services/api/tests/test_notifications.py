"""Notification delivery tests (G-15 / NG-4)."""

import uuid

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.enums import ProcessingStatus, ReportStatus
from app.models import FraudReport, PaymentEntity, User, UserNotification
from app.services import notifications


class _FakeChannel:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject))


def _enable_email(monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    monkeypatch.setattr(get_settings(), "notifications_email_enabled", enabled)


async def _make_user(db, email: str) -> User:
    user = User(email=email, password_hash="x")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_notify_writes_in_app_and_sends_email(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeChannel()
    monkeypatch.setattr(notifications, "get_channel", lambda: fake)
    _enable_email(monkeypatch, True)

    email = f"notif-{uuid.uuid4().hex[:8]}@x.dev"
    async with SessionLocal() as db:
        user = await _make_user(db, email)
        await notifications.notify(
            db,
            user_id=user.id,
            type="TEST",
            email_subject="Hello",
            email_body="Body",
        )
        rows = list(
            await db.scalars(select(UserNotification).where(UserNotification.user_id == user.id))
        )
    assert len(rows) == 1
    assert fake.sent and fake.sent[0][0] == email


async def test_notify_without_email_does_not_send(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeChannel()
    monkeypatch.setattr(notifications, "get_channel", lambda: fake)
    _enable_email(monkeypatch, False)

    async with SessionLocal() as db:
        user = await _make_user(db, f"notif-{uuid.uuid4().hex[:8]}@x.dev")
        await notifications.notify(
            db, user_id=user.id, type="TEST", email_subject="Hello", email_body="Body"
        )
    assert fake.sent == []


async def test_watcher_notification_emails_watcher_not_reporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeChannel()
    monkeypatch.setattr(notifications, "get_channel", lambda: fake)
    _enable_email(monkeypatch, True)

    async with SessionLocal() as db:
        watcher = await _make_user(db, f"watch-{uuid.uuid4().hex[:8]}@x.dev")
        reporter = await _make_user(db, f"rep-{uuid.uuid4().hex[:8]}@x.dev")
        entity = PaymentEntity(
            entity_type="BANK_ACCOUNT",
            scheme="BANK",
            country_code="ID",
            institution_code="014",
            account_hash=uuid.uuid4().hex,
            account_masked="500-****-111",
        )
        db.add(entity)
        await db.flush()
        report = FraudReport(
            payment_entity_id=entity.id,
            reporter_user_id=reporter.id,
            category="ONLINE_SHOP_GHOSTING",
            severity=3,
            description="x",
            processing_status=ProcessingStatus.PUBLISHED,
            status=ReportStatus.ACTIVE,
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)

        created = await notifications.notify_watchers(
            db,
            watcher_ids=[watcher.id, reporter.id],  # reporter is skipped
            reporter_user_id=reporter.id,
            entity_masked=entity.account_masked,
            entity_id=entity.id,
            report_id=report.id,
            category=report.category,
        )
    assert created == 1
    assert fake.sent == [(watcher.email, "New fraud report on 500-****-111")]
