"""Evidence upload safety (Phase 2.2, Doc 02 §9.1 H2).

Validate by magic bytes (not extension), enforce a decompression-bomb pixel cap
*before* decode, then re-encode through opencv to strip EXIF/GPS and kill
polyglots/SVG. Fail-closed: anything we cannot confidently normalize is rejected.
"""

from __future__ import annotations

import struct

import cv2
import numpy as np

from app.config import get_settings

JPEG = "image/jpeg"
PNG = "image/png"
WEBP = "image/webp"
_ALLOWED = (JPEG, PNG, WEBP)


class UploadValidationError(Exception):
    pass


def sniff_image(data: bytes) -> str:
    """Return the real MIME type from magic bytes, or raise."""
    if data[:3] == b"\xff\xd8\xff":
        return JPEG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return PNG
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return WEBP
    raise UploadValidationError("unsupported or non-image file (magic-byte check failed)")


def _png_dimensions(data: bytes) -> tuple[int, int]:
    # IHDR width/height are big-endian u32 at byte offsets 16 and 20.
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    i, n = 2, len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # SOF0..SOF15 except DHT(C4)/JPG(C8)/DAC(CC)
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        i += 2 + seg_len
    return None


def declared_pixels(data: bytes, content_type: str) -> int | None:
    """Pixel count parsed from the header, before any decode. None if unknown."""
    try:
        if content_type == PNG:
            w, h = _png_dimensions(data)
        elif content_type == JPEG:
            dims = _jpeg_dimensions(data)
            if dims is None:
                return None
            w, h = dims
        else:
            return None
    except (struct.error, IndexError):
        return None
    return w * h


class NormalizedImage:
    def __init__(self, data: bytes, content_type: str, width: int, height: int) -> None:
        self.data = data
        self.content_type = content_type
        self.width = width
        self.height = height


def normalize_image(data: bytes) -> NormalizedImage:
    """Validate + re-encode. Output is always JPEG (EXIF stripped)."""
    settings = get_settings()
    if not data:
        raise UploadValidationError("empty upload")
    if len(data) > settings.evidence_max_bytes:
        raise UploadValidationError("file too large")

    content_type = sniff_image(data)
    pixels = declared_pixels(data, content_type)
    if pixels is not None and pixels > settings.evidence_max_pixels:
        raise UploadValidationError("image exceeds maximum pixel count (decompression bomb guard)")

    buf = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if image is None:
        raise UploadValidationError("image could not be decoded")
    height, width = image.shape[:2]
    if width * height > settings.evidence_max_pixels:
        raise UploadValidationError("image exceeds maximum pixel count")

    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise UploadValidationError("image re-encode failed")
    return NormalizedImage(encoded.tobytes(), JPEG, int(width), int(height))
