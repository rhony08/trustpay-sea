"""WebAuthn (passkey) service — registration + authentication ceremonies (ADR-020).

Challenges live in Redis with a 60s single-use TTL: verify reads then deletes,
so a replayed ceremony payload cannot succeed.

Mandatory for ANALYST/SENIOR_ANALYST/SUPERADMIN when `MFA_REQUIRED_FOR_ADMINS=true`
(prod). Dev default false keeps the local loop usable; the login flow still
returns `mfa_required` for admin roles so the PWA exercises the ceremony path.
"""

import json
import time

import redis.asyncio as aioredis
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticationCredential,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import Settings

CHALLENGE_TTL_SECONDS = 60


class WebAuthnError(Exception):
    pass


def _challenge_key(user_id: str, purpose: str) -> str:
    return f"webauthn:{purpose}:{user_id}"


async def _store_challenge(
    redis: aioredis.Redis, user_id: str, purpose: str, challenge_b64url: str
) -> None:
    await redis.setex(_challenge_key(user_id, purpose), CHALLENGE_TTL_SECONDS, challenge_b64url)


async def _take_challenge(redis: aioredis.Redis, user_id: str, purpose: str) -> str:
    """Read + delete (single-use). Missing/expired challenge → error."""
    key = _challenge_key(user_id, purpose)
    value = await redis.get(key)
    if not value:
        raise WebAuthnError("challenge missing or expired")
    await redis.delete(key)
    return str(value)


async def registration_options(
    redis: aioredis.Redis, *, settings: Settings, user_id: str, email: str
) -> dict:
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_id.encode(),
        user_name=email,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    challenge = bytes_to_base64url(options.challenge)
    await _store_challenge(redis, user_id, "reg", challenge)
    return {
        "options": json.loads(options_to_json(options)),
        "challenge": challenge,
    }


async def verify_registration(
    redis: aioredis.Redis,
    *,
    settings: Settings,
    user_id: str,
    credential: RegistrationCredential,
    expected_challenge: str,
) -> dict:
    stored = await _take_challenge(redis, user_id, "reg")
    if stored != expected_challenge:
        raise WebAuthnError("challenge mismatch")
    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_origin=settings.webauthn_origin,
            expected_rp_id=settings.webauthn_rp_id,
            require_user_verification=False,
        )
    except WebAuthnError:
        raise
    except Exception as exc:  # webauthn lib raises its own error types
        raise WebAuthnError(f"registration verification failed: {exc}") from exc
    return {
        "credential_id": bytes_to_base64url(verification.credential_id),
        "public_key": bytes_to_base64url(verification.credential_public_key),
        "sign_count": verification.sign_count,
        "transports": list(credential.response.transports or []) if credential.response else [],
    }


async def authentication_options(
    redis: aioredis.Redis, *, settings: Settings, user_id: str, credentials: list
) -> dict:
    allow = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id)) for c in credentials
    ]
    auth_options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    challenge = bytes_to_base64url(auth_options.challenge)
    await _store_challenge(redis, user_id, "authn", challenge)
    return {"options": json.loads(options_to_json(auth_options)), "challenge": challenge}


async def verify_authentication(
    redis: aioredis.Redis,
    *,
    settings: Settings,
    user_id: str,
    credential: AuthenticationCredential,
    expected_challenge: str,
    stored_credential,
) -> int:
    """Returns new sign_count. Raises WebAuthnError on any verification failure."""
    stored = await _take_challenge(redis, user_id, "authn")
    if stored != expected_challenge:
        raise WebAuthnError("challenge mismatch")
    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_origin=settings.webauthn_origin,
            expected_rp_id=settings.webauthn_rp_id,
            credential_public_key=base64url_to_bytes(stored_credential.public_key),
            credential_current_sign_count=stored_credential.sign_count,
            require_user_verification=False,
        )
    except WebAuthnError:
        raise
    except Exception as exc:
        raise WebAuthnError(f"authentication verification failed: {exc}") from exc
    return verification.new_sign_count


def now() -> int:
    return int(time.time())
