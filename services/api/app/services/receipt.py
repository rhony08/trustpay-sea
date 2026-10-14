"""Diligence Receipt (Phase 3B.7) — tamper-evident proof of a pre-payment check.

A receipt records the masked entity + risk at check time, signed with HMAC so it
can be re-verified later. It is a point-in-time artifact, not a live risk score.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class ReceiptError(Exception):
    pass


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def create_receipt(secret: str, *, subject: dict[str, Any]) -> tuple[str, dict]:
    payload = {"v": 1, "at": int(time.time()), **subject}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    token = f"{base64.urlsafe_b64encode(body).decode()}.{_sign(secret, body)}"
    return token, payload


def verify_receipt(secret: str, token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        body = base64.urlsafe_b64decode(encoded.encode())
    except (ValueError, TypeError) as exc:
        raise ReceiptError("malformed receipt") from exc
    if not hmac.compare_digest(_sign(secret, body), signature):
        raise ReceiptError("receipt signature invalid")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ReceiptError("receipt payload unreadable") from exc
