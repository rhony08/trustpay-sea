"""Notification delivery (G-15 / NG-4).

In-app `user_notifications` rows are always written. Email is **opt-in**: when
`NOTIFICATIONS_EMAIL_ENABLED` is unset we use a console sender (logged, nothing
leaves the box), so dev/demo need no SMTP. Email delivery is best-effort and
never breaks the calling flow.

Channels are pluggable — swap `SmtpChannel` for Resend/Postmark later behind the
same `NotificationChannel` protocol.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from email.message import EmailMessage
from functools import lru_cache
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import User, UserNotification

log = logging.getLogger("trustpay.notifications")


class NotificationChannel(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleChannel:
    """Dev/default: log the email instead of sending it."""

    async def send(self, to: str, subject: str, body: str) -> None:
        log.info("email (console) to=%s subject=%r", to, subject)


class SmtpChannel:
    def __init__(self, settings: Settings) -> None:
        self._s = settings

    async def send(self, to: str, subject: str, body: str) -> None:
        def _send() -> None:
            message = EmailMessage()
            message["From"] = self._s.notifications_from_email
            message["To"] = to
            message["Subject"] = subject
            message.set_content(body)
            with smtplib.SMTP(self._s.smtp_host, self._s.smtp_port, timeout=10) as client:
                if self._s.smtp_starttls:
                    client.starttls()
                if self._s.smtp_user:
                    client.login(self._s.smtp_user, self._s.smtp_password or "")
                client.send_message(message)

        await asyncio.to_thread(_send)


@lru_cache(maxsize=1)
def get_channel() -> NotificationChannel:
    settings = get_settings()
    if settings.notifications_email_enabled and settings.smtp_host:
        return SmtpChannel(settings)
    return ConsoleChannel()


def reset_channel() -> None:
    get_channel.cache_clear()


async def notify(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    entity_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    email_subject: str | None = None,
    email_body: str | None = None,
) -> UserNotification:
    """Always write an in-app notification; email only when enabled + provided."""
    notification = UserNotification(
        user_id=user_id, type=type, entity_id=entity_id, payload=payload or {}
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    settings = get_settings()
    if settings.notifications_email_enabled and email_subject and email_body:
        user = await db.get(User, user_id)
        if user and user.email:
            try:
                await get_channel().send(user.email, email_subject, email_body)
            except Exception as exc:  # noqa: BLE001 — delivery must never break the caller
                log.warning("email notify failed for %s: %s", user_id, exc)
    return notification


async def notify_watchers(
    db: AsyncSession,
    *,
    watcher_ids: list[uuid.UUID],
    reporter_user_id: uuid.UUID | None,
    entity_masked: str,
    entity_id: uuid.UUID,
    report_id: uuid.UUID,
    category: str,
) -> int:
    created = 0
    for watcher_id in watcher_ids:
        if watcher_id == reporter_user_id:
            continue
        await notify(
            db,
            user_id=watcher_id,
            type="WATCHED_ENTITY_REPORT",
            entity_id=entity_id,
            payload={"report_id": str(report_id), "category": category},
            email_subject=f"New fraud report on {entity_masked}",
            email_body=(
                f"A new {category.replace('_', ' ').lower()} report was filed against an "
                f"account you watch ({entity_masked}).\n\nReview it on TrustPay SEA."
            ),
        )
        created += 1
    return created
