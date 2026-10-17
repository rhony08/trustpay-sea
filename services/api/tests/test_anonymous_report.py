"""Anonymous (no-login) report submission tests."""

import httpx
import pytest

PASSWORD = "s3cure-Passw0rd"


def _body(email: str, name: str, account: str = "8712345678") -> dict:
    return {
        "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": account},
        "category": "ONLINE_SHOP_GHOSTING",
        "severity": 3,
        "description": "Paid for an online order and the seller disappeared without shipping.",
        "consent": True,
        "reporter_email": email,
        "reporter_name": name,
    }


async def test_anonymous_new_email_creates_account_and_returns_token(
    client: httpx.AsyncClient,
) -> None:
    resp = await client.post("/api/v1/reports/anonymous", json=_body("anon-new@trustpay.dev", "Anon New"))
    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    assert data["reporter"]["is_new"] is True
    assert data["reporter"]["name"] == "Anon New"
    assert data["access_token"]  # new account → session issued

    # token works for polling the report
    view = await client.get(
        f"/api/v1/reports/{data['report_id']}",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert view.status_code == 200


async def test_anonymous_existing_email_uses_registered_name_and_no_token(
    client: httpx.AsyncClient,
) -> None:
    # register the account first (its display name is what must be used)
    reg = await client.post(
        "/api/v1/auth/signup",
        json={"email": "anon-existing@trustpay.dev", "password": PASSWORD, "display_name": "Registered Name"},
    )
    assert reg.status_code == 201, reg.text

    resp = await client.post(
        "/api/v1/reports/anonymous",
        json=_body("anon-existing@trustpay.dev", "Different Claimed Name"),
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    assert data["reporter"]["is_new"] is False
    assert data["reporter"]["name"] == "Registered Name"  # registered name wins
    assert "access_token" not in data  # never issue a session for an existing account


async def test_anonymous_requires_consent(client: httpx.AsyncClient) -> None:
    body = _body("anon-consent@trustpay.dev", "No Consent")
    body["consent"] = False
    resp = await client.post("/api/v1/reports/anonymous", json=body)
    assert resp.status_code == 400
