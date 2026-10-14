"""Vision: PII redaction of evidence (Phase 2.3).

Mock-first (ADR-012 / G-9): no Gemini key required. The contract is what matters
for MVP — redaction is **fail-closed**. If it raises, the worker must NOT
publish the evidence (report → FAILED). The real Gemini-Vision redactor slots in
behind this function; the fail-closed guarantee stays in the caller.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.config import get_settings


class RedactionError(Exception):
    pass


def redact_image(data: bytes) -> bytes:
    """Return a redacted JPEG copy of the evidence.

    Mock behaviour blurs a horizontal band (where balances/names typically sit)
    so the pipeline and public-copy plumbing are exercised end-to-end.
    """
    settings = get_settings()
    if settings.ai_redaction_always_fail:
        raise RedactionError("PII redaction failed (fail-closed)")

    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise RedactionError("redaction could not decode image")

    height, width = image.shape[:2]
    top, bottom = int(height * 0.30), int(height * 0.70)
    band = image[top:bottom, :]
    if band.size:
        k = max(3, (width // 40) | 1)
        image[top:bottom, :] = cv2.GaussianBlur(band, (k, k), 0)

    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RedactionError("redaction re-encode failed")
    return encoded.tobytes()
