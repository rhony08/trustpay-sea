"""Server-side QR decode from image bytes (Phase 1.4, ADR-001).

The browser decodes for instant preview (html5-qrcode, Phase 1.6); the server
ALWAYS re-decodes and re-parses — client claims are never trusted.
"""

from app.resolver.emvco import EMVCoParseError

MAX_IMAGE_BYTES = 4 * 1024 * 1024  # 4MB upload cap
MAX_PIXELS = 25_000_000  # decompression-bomb guard (Doc 02 §9.1)


class QRDecodeError(Exception):
    pass


def decode_qr_payload(image_bytes: bytes) -> str:
    """Decode the first QR code found in the image → raw EMVCo string."""
    if not image_bytes:
        raise QRDecodeError("empty image")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise QRDecodeError(f"image exceeds {MAX_IMAGE_BYTES} bytes")

    try:
        import cv2  # noqa: PLC0415 — heavy import, keep module import light
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise QRDecodeError("opencv not installed") from exc

    if len(image_bytes) >= 12 and image_bytes[4:12].startswith(b"ftyp"):
        raise QRDecodeError("unsupported format (video/heic container)")

    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise QRDecodeError("could not decode image (corrupt or non-image data)")

    height, width = image.shape[:2]
    if width * height > MAX_PIXELS:
        raise QRDecodeError(f"image exceeds {MAX_PIXELS} pixels")

    detector = cv2.QRCodeDetector()
    # detectAndDecodeMulti arity differs across cv2 builds (3 vs 4 return values)
    multi = detector.detectAndDecodeMulti(image)
    text = ""
    if multi and multi[0]:
        decoded_info = multi[1]
        if isinstance(decoded_info, (list, tuple)):
            text = next((t for t in decoded_info if t), "")
        elif decoded_info:
            text = str(decoded_info)
    if not text:
        single, _pts = detector.detect(image)
        if single:
            text, _ = detector.decode(image)
    if not text:
        raise QRDecodeError("no QR code found in image")
    if isinstance(text, tuple):
        text = next((t for t in text if t), "")
    if not text:
        raise QRDecodeError("no QR code found in image")
    return text.strip()


def decode_and_parse(image_bytes: bytes) -> str:
    """Decode QR image and validate it parses as EMVCo — convenience for routes."""
    from app.resolver.emvco import parse_emvco  # noqa: PLC0415

    payload = decode_qr_payload(image_bytes)
    try:
        parse_emvco(payload)
    except EMVCoParseError as exc:
        raise QRDecodeError(f"QR decoded but not valid EMVCo: {exc}") from exc
    return payload
