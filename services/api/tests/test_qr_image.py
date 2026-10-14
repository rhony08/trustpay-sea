"""Server-side QR decode from image (Phase 1.4, ADR-001).

Uses the committed fixture PNG (packages/test-vectors/qris_static.png) — the
cv2 QRCodeEncoder segfaults in some arm64 wheels, so the QR image is generated
once (dev-side, `qrcode` lib) and committed rather than rendered in tests.
Also guards the upload defensive checks (empty, oversized, non-image).
"""

from pathlib import Path

import pytest

from app.resolver.emvco import parse_emvco
from app.resolver.qr_image import (
    MAX_IMAGE_BYTES,
    QRDecodeError,
    decode_and_parse,
    decode_qr_payload,
)

VECTORS = Path(__file__).resolve().parents[3] / "packages" / "test-vectors"
QRIS = (VECTORS / "qris_static.txt").read_text().strip()
QRIS_PNG = (VECTORS / "qris_static.png").read_bytes()


def test_qr_image_roundtrip() -> None:
    decoded = decode_qr_payload(QRIS_PNG)
    assert decoded == QRIS
    parsed = parse_emvco(decoded)
    assert parsed.merchant_name == "CV ELEKTRONIK JAYA MURAH"
    assert parsed.scheme.value == "QRIS"


def test_decode_and_parse_helper() -> None:
    assert decode_and_parse(QRIS_PNG) == QRIS


def test_empty_image_rejected() -> None:
    with pytest.raises(QRDecodeError, match="empty"):
        decode_qr_payload(b"")


def test_oversized_bytes_rejected() -> None:
    with pytest.raises(QRDecodeError, match="exceeds"):
        decode_qr_payload(b"x" * (MAX_IMAGE_BYTES + 1))


def test_non_image_rejected() -> None:
    with pytest.raises(QRDecodeError):
        decode_qr_payload(b"this is definitely not an image at all, sorry")


async def test_api_decode_endpoint_roundtrip(client) -> None:
    """POST /api/v1/qr/decode → payload + parsed metadata (server-authoritative)."""
    resp = await client.post(
        "/api/v1/qr/decode",
        files={"file": ("qris.png", QRIS_PNG, "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["qr_payload"] == QRIS
    assert body["data"]["qr_metadata"]["merchant_name"] == "CV ELEKTRONIK JAYA MURAH"


async def test_api_decode_non_image_400(client) -> None:
    resp = await client.post(
        "/api/v1/qr/decode",
        files={"file": ("fake.png", b"not an image", "image/png")},
    )
    assert resp.status_code == 400
