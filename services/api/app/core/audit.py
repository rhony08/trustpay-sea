"""Hash-chained, append-only audit log (Doc 02 §9.3, C-A4 / ADR-013).

Each row's `row_hash = SHA256(prev_hash + canonical(fields))`. Any UPDATE/DELETE
breaks the chain and is caught by the nightly reconciler (Phase 7). Used for
trust-altering admin actions (flag resolution, bans, gov overrides).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def compute_row_hash(prev_hash: str | None, fields: dict[str, Any]) -> str:
    payload = json.dumps({"prev": prev_hash, **fields}, sort_keys=True, default=str).encode()
    return hashlib.sha256(payload).hexdigest()


async def append_audit(
    db: AsyncSession,
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    note: str | None = None,
) -> AuditLog:
    prev_hash = await db.scalar(select(AuditLog.row_hash).order_by(AuditLog.id.desc()).limit(1))
    fields = {
        "action": action,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "subject_type": subject_type,
        "subject_id": str(subject_id) if subject_id else None,
        "before": before,
        "after": after,
        "note": note,
    }
    row = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        before=before,
        after=after,
        note=note,
        prev_hash=prev_hash,
        row_hash=compute_row_hash(prev_hash, fields),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def verify_chain(db: AsyncSession, *, limit: int = 1000) -> bool:
    """Recompute a window of the chain; returns False on the first mismatch."""
    rows = list(await db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)))
    rows.reverse()
    prev: str | None = None
    for row in rows:
        if row.prev_hash != prev:
            return False
        fields = {
            "action": row.action,
            "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
            "subject_type": row.subject_type,
            "subject_id": str(row.subject_id) if row.subject_id else None,
            "before": row.before,
            "after": row.after,
            "note": row.note,
        }
        if compute_row_hash(prev, fields) != row.row_hash:
            return False
        prev = row.row_hash
    return True
