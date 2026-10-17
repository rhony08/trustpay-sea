"""Evidence image compression tests (storage saving)."""

import cv2
import numpy as np

from app.services.image_guard import JPEG, normalize_image


def _gradient_png(width: int, height: int) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[..., 0] = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
    img[..., 1] = np.linspace(0, 255, width, dtype=np.uint8)[None, :]
    ok, encoded = cv2.imencode(".png", img)
    assert ok
    return encoded.tobytes()


def test_large_image_is_downscaled_and_compressed() -> None:
    data = _gradient_png(3200, 2400)
    out = normalize_image(data)
    assert out.content_type == JPEG
    assert max(out.width, out.height) <= 1920  # long edge capped
    assert len(out.data) < len(data)  # smaller on disk


def test_small_image_keeps_dimensions() -> None:
    out = normalize_image(_gradient_png(400, 300))
    assert (out.width, out.height) == (400, 300)
