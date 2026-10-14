"""Forensics: slip OCR, tamper heuristics, perceptual hashing (Phases 2.4/2.5).

Mock-first (ADR-012): OCR/tamper are stubbed but the interfaces and the pHash
duplicate detector are real. OCR output is untrusted text — it is only ever
stored as data and masked before any public surface.
"""

from __future__ import annotations

import cv2
import numpy as np


def ocr_slip(data: bytes) -> dict:
    """Extract {sender, recipient, ref_id, time, amount} from a transfer slip.

    Mock: returns an empty structured shell. Real OCR plugs in here.
    """
    _ = data
    return {"engine": "mock", "text": "", "fields": {}}


def detect_tampering(data: bytes) -> tuple[bool, dict]:
    """Tamper heuristic (Doc 02 §4.2 MVP subset). Informs, never auto-rejects."""
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return False, {"engine": "mock", "signals": []}
    # Cheap proxy: unusually high edge density suggests re-pasted/edited text.
    edges = cv2.Canny(image, 100, 200)
    density = float(np.count_nonzero(edges)) / float(edges.size)
    signals = ["high_edge_density"] if density > 0.30 else []
    return bool(signals), {"engine": "mock", "edge_density": round(density, 4), "signals": signals}


def phash(data: bytes, hash_size: int = 8) -> str:
    """Difference hash (dHash) as hex — detects the same image reused across reports."""
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError("phash could not decode image")
    resized = cv2.resize(image, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = np.packbits(diff.flatten())
    return bits.tobytes().hex()


def hamming_distance(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b)) * 4
    return bin(int(a, 16) ^ int(b, 16)).count("1")
