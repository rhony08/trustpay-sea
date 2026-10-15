"""ADR-020: cookie sessions, CSRF double-submit, WebAuthn MFA, step-up guard.

Virtual authenticator: a software ES256 "authenticator" builds registration and
authentication credentials by hand (CBOR COSE key + authData + signature) so the
full py_webauthn verification path runs without a browser.
"""

import base64
import hashlib
import json
import os
import time
import uuid

import cbor2
import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import get_settings
from app.core.security import JWTService

RP_ID = "localhost"
ORIGIN = "http://localhost:3000"


# ---------------------------------------------------------------- virtual authn


class VirtualAuthenticator:
    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.sign_count = 0

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    def _client_data(self, typ: str, challenge_b64: str) -> bytes:
        return json.dumps(
            {
                "type": typ,
                "challenge": challenge_b64,
                "origin": ORIGIN,
                "crossOrigin": False,
            }
        ).encode()

    def _auth_data(self, *, attested: bool) -> bytes:
        flags = 0x45 if attested else 0x05  # UP | (AT if registration)
        rp_hash = hashlib.sha256(RP_ID.encode()).digest()
        header = rp_hash + bytes([flags]) + self.sign_count.to_bytes(4, "big")
        if not attested:
            return header
        aaguid = b"\x00" * 16  # AAGUID — parsers expect 16 bytes before credIdLen
        cred_len = len(self.credential_id).to_bytes(2, "big")
        return header + aaguid + cred_len + self.credential_id + self._cose_public_key()

    def _cose_public_key(self) -> bytes:
        pub = self.key.public_key().public_numbers()
        return cbor2.dumps(
            {1: 2, 3: -7, -1: 1, -2: pub.x.to_bytes(32, "big"), -3: pub.y.to_bytes(32, "big")}
        )

    def _sign(self, data: bytes) -> bytes:
        # py_webauthn 3.x feeds the signature straight to cryptography's verify,
        # which wants DER — not the raw R||S authenticators send on the wire.
        return self.key.sign(data, ec.ECDSA(hashes.SHA256()))

    def register(self, challenge_b64: str) -> dict:
        client_data = self._client_data("webauthn.create", challenge_b64)
        auth_data = self._auth_data(attested=True)
        att_obj = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": self._b64(self.credential_id),
            "rawId": self._b64(self.credential_id),
            "response": {
                "clientDataJSON": self._b64(client_data),
                "attestationObject": self._b64(att_obj),
                "transports": ["internal"],
            },
            "type": "public-key",
        }

    def authenticate(self, challenge_b64: str) -> dict:
        self.sign_count += 1
        client_data = self._client_data("webauthn.get", challenge_b64)
        auth_data = self._auth_data(attested=False)
        signature = self._sign(auth_data + hashlib.sha256(client_data).digest())
        return {
            "id": self._b64(self.credential_id),
            "rawId": self._b64(self.credential_id),
            "response": {
                "clientDataJSON": self._b64(client_data),
                "authenticatorData": self._b64(auth_data),
                "signature": self._b64(signature),
                "userHandle": None,
            },
            "type": "public-key",
        }


# ---------------------------------------------------------------- helpers

PASSWORD = "s3cure-Passw0rd"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _signup(client: httpx.AsyncClient, email: str) -> dict:
    resp = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": PASSWORD},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(client: httpx.AsyncClient, email: str):
    return await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})


def _require_mfa_env(monkeypatch) -> None:
    monkeypatch.setenv("MFA_REQUIRED_FOR_ADMINS", "true")
    monkeypatch.setenv("MFA_STEP_UP_SECONDS", "300")
    get_settings.cache_clear()


# ---------------------------------------------------------------- CSRF


async def test_cookie_authenticated_mutation_requires_csrf(client: httpx.AsyncClient) -> None:
    """Cookie session + mutating request without X-CSRF-Token → 403; with it → works."""
    await _signup(client, "csrf-user@trustpay.dev")

    # login again through the API so the client holds tp_* cookies
    await _login(client, "csrf-user@trustpay.dev")
    assert "tp_access" in client.cookies
    assert "tp_csrf" in client.cookies

    body = {
        "target": {"kind": "ACCOUNT", "country": "ID", "bank": "014", "account": "8830192831"},
        "category": "OTHER",
        "severity": 3,
        "description": "cookie flow without csrf header",
        "consent": True,
    }
    no_csrf = await client.post("/api/v1/reports", json=body)
    assert no_csrf.status_code == 403
    assert "CSRF" in no_csrf.json()["detail"]

    with_csrf = await client.post(
        "/api/v1/reports",
        json=body,
        headers={"X-CSRF-Token": client.cookies.get("tp_csrf")},
    )
    assert with_csrf.status_code == 202, with_csrf.text


async def test_bearer_mutation_needs_no_csrf(client: httpx.AsyncClient) -> None:
    tokens = await _signup(client, "csrf-bearer@trustpay.dev")
    await _login(client, "csrf-bearer@trustpay.dev")  # cookies present
    # explicit Authorization header wins — CSRF does not apply
    resp = await client.post(
        "/api/v1/reports",
        json={
            "target": {
                "kind": "ACCOUNT",
                "country": "ID",
                "bank": "014",
                "account": "8830192832",
            },
            "category": "OTHER",
            "severity": 3,
            "description": "bearer flow description long enough",
            "consent": True,
        },
        headers=_auth(tokens["access_token"]),
    )
    assert resp.status_code == 202, resp.text


# ---------------------------------------------------------------- WebAuthn MFA


async def test_admin_login_without_credential_blocked_when_mfa_required(
    client: httpx.AsyncClient, monkeypatch
) -> None:
    await _signup(client, "mfa-admin@trustpay.dev")
    from app.db import SessionLocal
    from app.enums import Role

    async with SessionLocal() as db:
        user = await db.scalar(select_user("mfa-admin@trustpay.dev"))
        user.role = Role.ANALYST
        await db.commit()

    _require_mfa_env(monkeypatch)
    resp = await _login(client, "mfa-admin@trustpay.dev")
    assert resp.status_code == 403
    assert "passkey" in resp.json()["detail"]
    get_settings.cache_clear()


def select_user(email: str):
    from sqlalchemy import select

    from app.models import User

    return select(User).where(User.email == email)


async def test_admin_login_returns_mfa_challenge_and_ceremony_issues_cookies(
    client: httpx.AsyncClient,
) -> None:
    tokens = await _signup(client, "mfa-admin2@trustpay.dev")
    authn = VirtualAuthenticator()

    # enroll a passkey while still a regular user
    reg_options = await client.post(
        "/api/v1/auth/webauthn/register/options", headers=_auth(tokens["access_token"])
    )
    reg = reg_options.json()
    enrolled = await client.post(
        "/api/v1/auth/webauthn/register/verify",
        json={"challenge": reg["challenge"], "credential": authn.register(reg["challenge"])},
        headers=_auth(tokens["access_token"]),
    )
    assert enrolled.status_code == 201, enrolled.text

    # promote to ANALYST → login must demand MFA (credential exists)
    from app.db import SessionLocal
    from app.enums import Role

    async with SessionLocal() as db:
        user = await db.scalar(select_user("mfa-admin2@trustpay.dev"))
        user.role = Role.ANALYST
        await db.commit()

    login = await _login(client, "mfa-admin2@trustpay.dev")
    assert login.status_code == 200
    challenge = login.json()
    assert challenge["mfa_required"] is True
    mfa_token = challenge["mfa_token"]

    options = await client.post("/api/v1/auth/mfa/webauthn/options", json={"mfa_token": mfa_token})
    assert options.status_code == 200
    payload = options.json()
    verified = await client.post(
        "/api/v1/auth/mfa/webauthn/verify",
        json={
            "mfa_token": mfa_token,
            "challenge": payload["challenge"],
            "credential": authn.authenticate(payload["challenge"]),
        },
    )
    assert verified.status_code == 200, verified.text
    assert "tp_access" in client.cookies


async def test_full_mfa_login_flow_with_virtual_authenticator(client: httpx.AsyncClient) -> None:
    tokens = await _signup(client, "mfa-full@trustpay.dev")
    authn = VirtualAuthenticator()

    # 1. enroll a passkey
    reg_options = await client.post(
        "/api/v1/auth/webauthn/register/options", headers=_auth(tokens["access_token"])
    )
    reg = reg_options.json()
    enrolled = await client.post(
        "/api/v1/auth/webauthn/register/verify",
        json={"challenge": reg["challenge"], "credential": authn.register(reg["challenge"])},
        headers=_auth(tokens["access_token"]),
    )
    assert enrolled.status_code == 201, enrolled.text

    # 2. user upgrades to ANALYST → login must demand MFA even in dev
    from app.db import SessionLocal
    from app.enums import Role

    async with SessionLocal() as db:
        user = await db.scalar(select_user("mfa-full@trustpay.dev"))
        user.role = Role.ANALYST
        await db.commit()

    login = await _login(client, "mfa-full@trustpay.dev")
    assert login.json().get("mfa_required") is True
    mfa_token = login.json()["mfa_token"]

    # 3. ceremony
    options = await client.post("/api/v1/auth/mfa/webauthn/options", json={"mfa_token": mfa_token})
    assert options.status_code == 200
    payload = options.json()
    verified = await client.post(
        "/api/v1/auth/mfa/webauthn/verify",
        json={
            "mfa_token": mfa_token,
            "challenge": payload["challenge"],
            "credential": authn.authenticate(payload["challenge"]),
        },
    )
    assert verified.status_code == 200, verified.text
    assert "tp_access" in client.cookies

    # 4. mfa_at claim present → step-up guard passes
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200

    # 5. challenge replay fails (single-use)
    replay = await client.post(
        "/api/v1/auth/mfa/webauthn/verify",
        json={
            "mfa_token": mfa_token,
            "challenge": payload["challenge"],
            "credential": authn.authenticate(payload["challenge"]),
        },
    )
    assert replay.status_code == 401


async def test_step_up_guard_blocks_without_mfa_claim(client: httpx.AsyncClient) -> None:
    """When MFA is required, an access token without mfa_at cannot act on approvals."""
    await _signup(client, "stepup@trustpay.dev")
    from app.db import SessionLocal
    from app.enums import Role

    async with SessionLocal() as db:
        user = await db.scalar(select_user("stepup@trustpay.dev"))
        user.role = Role.ANALYST
        await db.commit()

    settings = get_settings()
    jwt = JWTService(settings)
    no_mfa_access, _aj, _rj = jwt.issue_token_pair(user_id=str(user.id), role=Role.ANALYST)
    fresh_access, _aj2, _rj2 = jwt.issue_token_pair(
        user_id=str(user.id), role=Role.ANALYST, mfa_at=int(time.time())
    )

    body = {
        "action": "ban_user",
        "subject_type": "user",
        "subject_id": str(uuid.uuid4()),
    }

    monkey_env_off = get_settings().mfa_required_for_admins
    try:
        import os

        os.environ["MFA_REQUIRED_FOR_ADMINS"] = "true"
        get_settings.cache_clear()

        blocked = await client.post(
            "/api/v1/admin/approvals", json=body, headers=_auth(no_mfa_access.access_token)
        )
        assert blocked.status_code == 403
        assert "MFA" in blocked.json()["detail"]

        fresh = await client.post(
            "/api/v1/admin/approvals", json=body, headers=_auth(fresh_access.access_token)
        )
        assert fresh.status_code == 201, fresh.text
    finally:
        if monkey_env_off:
            os.environ["MFA_REQUIRED_FOR_ADMINS"] = "true"
        else:
            os.environ["MFA_REQUIRED_FOR_ADMINS"] = "false"
        get_settings.cache_clear()


async def test_admin_requires_passkey_when_strictly_required(
    client: httpx.AsyncClient, monkeypatch
) -> None:
    """Prod gate: MFA_REQUIRED_FOR_ADMINS=true + no credential → no admin login."""
    await _signup(client, "strict-admin@trustpay.dev")
    from app.db import SessionLocal
    from app.enums import Role

    async with SessionLocal() as db:
        user = await db.scalar(select_user("strict-admin@trustpay.dev"))
        user.role = Role.SUPERADMIN
        await db.commit()

    _require_mfa_env(monkeypatch)
    resp = await _login(client, "strict-admin@trustpay.dev")
    assert resp.status_code == 403
    get_settings.cache_clear()
