"""ADR-021: dual-control coverage — expiry, cancel, and queue semantics."""

import uuid
from datetime import UTC, datetime, timedelta

import httpx

from app.db import SessionLocal
from app.models import AdminApproval


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


PASSWORD = "s3cure-Passw0rd"


async def _signup(client: httpx.AsyncClient, email: str) -> dict:
    resp = await client.post("/api/v1/auth/signup", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _make_admin(client: httpx.AsyncClient, email: str) -> dict:
    tokens = await _signup(client, email)
    from sqlalchemy import select

    from app.enums import Role
    from app.models import User

    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        user.role = Role.ANALYST
        await db.commit()
    return tokens


async def _create_approval(client: httpx.AsyncClient, admin_token: str) -> str:
    resp = await client.post(
        "/api/v1/admin/approvals",
        json={
            "action": "ban_user",
            "subject_type": "user",
            "subject_id": str(uuid.uuid4()),
        },
        headers=_auth(admin_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def test_approval_set_with_72h_expiry(client: httpx.AsyncClient) -> None:
    admin = await _make_admin(client, "exp-a@trustpay.dev")
    approval_id = await _create_approval(client, admin["access_token"])
    async with SessionLocal() as db:
        approval = await db.get(AdminApproval, uuid.UUID(approval_id))
        assert approval is not None
        assert approval.expires_at is not None
        delta = approval.expires_at - datetime.now(UTC)
        assert timedelta(hours=71) < delta <= timedelta(hours=72)


async def test_expired_approval_cannot_be_cashed_in(client: httpx.AsyncClient) -> None:
    first = await _make_admin(client, "exp2-a@trustpay.dev")
    second = await _make_admin(client, "exp2-b@trustpay.dev")
    approval_id = await _create_approval(client, first["access_token"])
    async with SessionLocal() as db:
        approval = await db.get(AdminApproval, uuid.UUID(approval_id))
        approval.expires_at = datetime.now(UTC) - timedelta(hours=1)
        await db.commit()

    resp = await client.post(
        f"/api/v1/admin/approvals/{approval_id}/approve", headers=_auth(second["access_token"])
    )
    assert resp.status_code == 409
    assert "expired" in resp.json()["detail"]


async def test_only_requester_can_cancel(client: httpx.AsyncClient) -> None:
    first = await _make_admin(client, "cancel-a@trustpay.dev")
    second = await _make_admin(client, "cancel-b@trustpay.dev")
    approval_id = await _create_approval(client, first["access_token"])

    not_requester = await client.post(
        f"/api/v1/admin/approvals/{approval_id}/cancel", headers=_auth(second["access_token"])
    )
    assert not_requester.status_code == 409

    cancelled = await client.post(
        f"/api/v1/admin/approvals/{approval_id}/cancel", headers=_auth(first["access_token"])
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "CANCELLED"

    # a cancelled approval cannot later be approved
    late = await client.post(
        f"/api/v1/admin/approvals/{approval_id}/approve", headers=_auth(second["access_token"])
    )
    assert late.status_code == 409


async def test_new_actions_accepted_by_api(client: httpx.AsyncClient) -> None:
    """hide_report / remove_report / settlement are valid approval actions (ADR-021)."""
    admin = await _make_admin(client, "actions-a@trustpay.dev")
    for action in ("hide_report", "remove_report", "settlement"):
        resp = await client.post(
            "/api/v1/admin/approvals",
            json={
                "action": action,
                "subject_type": "review_flag" if action == "hide_report" else "owner_dispute",
                "subject_id": str(uuid.uuid4()),
                "payload": {},
            },
            headers=_auth(admin["access_token"]),
        )
        assert resp.status_code == 201, f"{action}: {resp.text}"


async def test_unknown_action_rejected(client: httpx.AsyncClient) -> None:
    admin = await _make_admin(client, "actions-b@trustpay.dev")
    resp = await client.post(
        "/api/v1/admin/approvals",
        json={
            "action": "destroy_everything",
            "subject_type": "user",
            "subject_id": str(uuid.uuid4()),
        },
        headers=_auth(admin["access_token"]),
    )
    assert resp.status_code == 422  # pydantic pattern rejects before the service
