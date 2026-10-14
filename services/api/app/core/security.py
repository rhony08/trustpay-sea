"""Security primitives: argon2id hashing, RS256 JWT with rotation + reuse detection.

Invariants (Doc 02 §9.2):
- argon2id password hashing
- RS256 pinned (reject none / alg-confusion)
- audience/issuer validation
- refresh rotation with reuse detection (family revocation)
"""

import base64
import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import Settings
from app.enums import Role

_hasher = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class TokenError(Exception):
    pass


class JWTService:
    """RS256 JWT issuer. Private key stays on the server; public key verifies."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._private_key = Path(settings.jwt_private_key_path).read_text()
        self._public_key = Path(settings.jwt_public_key_path).read_text()

    def _issue(
        self,
        *,
        sub: str,
        role: str,
        token_type: str,
        ttl_seconds: int,
        family: str | None = None,
    ) -> str:
        now = int(time.time())
        jti = uuid.uuid4().hex
        payload = {
            "sub": sub,
            "role": role,
            "typ": token_type,
            "jti": jti,
            "iss": self._settings.issuer,
            "aud": self._settings.audience,
            "iat": now,
            "nbf": now,
            "exp": now + ttl_seconds,
        }
        if family:
            payload["fam"] = family
        return jwt.encode(payload, self._private_key, algorithm=self._settings.jwt_algorithm)

    def decode(self, token: str, *, expected_type: str) -> dict:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=[self._settings.jwt_algorithm],  # pinned — no alg from token
                issuer=self._settings.issuer,
                audience=self._settings.audience,
                options={"require": ["exp", "iat", "sub", "typ", "jti"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenError(f"invalid token: {exc}") from exc
        if payload.get("typ") != expected_type:
            raise TokenError(f"wrong token type: expected {expected_type}")
        return payload

    def issue_token_pair(
        self, *, user_id: str, role: Role | str, family: str | None = None
    ) -> tuple[TokenPair, str, str]:
        """Returns (pair, access_jti, refresh_jti). Family id created if None."""
        fam = family or uuid.uuid4().hex
        access = self._issue(
            sub=user_id,
            role=str(role),
            token_type="access",
            ttl_seconds=self._settings.access_token_ttl_seconds,
        )
        refresh = self._issue(
            sub=user_id,
            role=str(role),
            token_type="refresh",
            ttl_seconds=self._settings.refresh_token_ttl_seconds,
            family=fam,
        )
        access_jti = self.decode(access, expected_type="access")["jti"]
        refresh_jti = self.decode(refresh, expected_type="refresh")["jti"]
        return (
            TokenPair(
                access_token=access,
                refresh_token=refresh,
                expires_in=self._settings.access_token_ttl_seconds,
            ),
            access_jti,
            refresh_jti,
        )


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")
