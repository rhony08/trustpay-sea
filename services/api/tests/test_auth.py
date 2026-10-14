import httpx
import pytest

EMAIL = "tester@trustpay.dev"
PASSWORD = "s3cure-Passw0rd"


async def _signup(client: httpx.AsyncClient, email: str = EMAIL) -> dict:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": PASSWORD, "display_name": "Tester"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_signup_login_me_roundtrip(client: httpx.AsyncClient) -> None:
    tokens = await _signup(client, email="roundtrip@trustpay.dev")
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "roundtrip@trustpay.dev"
    assert body["role"] == "USER"
    assert body["identity_trust"] == 10  # ADR-014: new accounts start LOW


async def test_duplicate_signup_conflict(client: httpx.AsyncClient) -> None:
    await _signup(client, email="dup@trustpay.dev")
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@trustpay.dev", "password": PASSWORD},
    )
    assert resp.status_code == 409


async def test_login_wrong_password_401(client: httpx.AsyncClient) -> None:
    await _signup(client, email="wrongpw@trustpay.dev")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@trustpay.dev", "password": "not-the-password"},
    )
    assert resp.status_code == 401


async def test_refresh_rotation_and_reuse_detection(client: httpx.AsyncClient) -> None:
    tokens = await _signup(client, email="rotate@trustpay.dev")

    # rotate once — get new pair
    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200
    rotated = r1.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # presenting the OLD (burned) token again = reuse → family revoked
    reuse = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse.status_code == 401
    assert "reuse" in reuse.json()["detail"]

    # the rotated token also dies with the family
    after = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
    )
    assert after.status_code == 401


async def test_logout_revokes_family(client: httpx.AsyncClient) -> None:
    tokens = await _signup(client, email="logout@trustpay.dev")
    out = await client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert out.status_code == 204
    after = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert after.status_code == 401


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_rbac_analyst_gate(client: httpx.AsyncClient) -> None:
    tokens = await _signup(client, email="user-rbac@trustpay.dev")
    resp = await client.get(
        "/protected-ping", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 403  # USER < ANALYST


@pytest.mark.asyncio
async def test_password_not_stored_in_plaintext(client: httpx.AsyncClient) -> None:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User

    await _signup(client, email="hashcheck@trustpay.dev")
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == "hashcheck@trustpay.dev"))
        assert user is not None
        assert user.password_hash is not None
        assert PASSWORD not in user.password_hash
        assert user.password_hash.startswith("$argon2")
