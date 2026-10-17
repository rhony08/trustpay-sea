"""Anonymous report-scoped evidence token."""

from pathlib import Path

import httpx

VECTORS = Path(__file__).resolve().parents[3] / "packages" / "test-vectors"
PNG = (VECTORS / "qris_static.png").read_bytes()
PASSWORD = "s3cure-Passw0rd"


def _body(email: str, name: str, account: str) -> dict:
    return {
        "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": account},
        "category": "ONLINE_SHOP_GHOSTING",
        "severity": 3,
        "description": "Paid for an online order and the seller never shipped it.",
        "consent": True,
        "reporter_email": email,
        "reporter_name": name,
    }


async def test_evidence_token_uploads_for_registered_email(client: httpx.AsyncClient) -> None:
    # registered email → no session, but an evidence token is still issued
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "evtok@trustpay.dev", "password": PASSWORD, "display_name": "Ev Tok"},
    )
    created = await client.post(
        "/api/v1/reports/anonymous", json=_body("evtok@trustpay.dev", "X", "8711112222")
    )
    data = created.json()["data"]
    assert "access_token" not in data
    token = data["evidence_token"]
    assert token
    rid = data["report_id"]

    up = await client.post(
        f"/api/v1/reports/{rid}/evidence",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("slip.png", PNG, "image/png")},
        data={"media_type": "TRANSFER_SLIP"},
    )
    assert up.status_code == 202, up.text


async def test_evidence_token_is_scoped_to_its_report(client: httpx.AsyncClient) -> None:
    a = await client.post(
        "/api/v1/reports/anonymous", json=_body("evscope-a@trustpay.dev", "A", "8711114444")
    )
    b = await client.post(
        "/api/v1/reports/anonymous", json=_body("evscope-b@trustpay.dev", "B", "8711115555")
    )
    token_a = a.json()["data"]["evidence_token"]
    rid_b = b.json()["data"]["report_id"]

    up = await client.post(
        f"/api/v1/reports/{rid_b}/evidence",
        headers={"Authorization": f"Bearer {token_a}"},
        files={"file": ("slip.png", PNG, "image/png")},
        data={"media_type": "TRANSFER_SLIP"},
    )
    assert up.status_code == 403
