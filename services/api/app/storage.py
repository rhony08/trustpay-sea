"""Evidence object storage (Phase 2.2).

Public evidence is *always* the redacted copy; originals live in a private
quarantine area. Dev uses a local-disk shim; production swaps in R2/S3 presigned
uploads behind the same interface (Phase 7). Quarantine objects are never served
on the public base URL.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings


class StorageError(Exception):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str  # storage-relative key (NOT a public URL)
    content_type: str
    size: int


class Storage(Protocol):
    def put_quarantine(self, *, data: bytes, content_type: str) -> StoredObject: ...
    def put_public(self, *, data: bytes, content_type: str) -> StoredObject: ...
    def read(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def public_url(self, key: str) -> str: ...
    def presign_put(self, *, content_type: str) -> dict: ...


_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _new_key(area: str, content_type: str) -> str:
    ext = _EXT_BY_TYPE.get(content_type, "bin")
    return f"{area}/{uuid.uuid4().hex}.{ext}"


class LocalStorage:
    """Filesystem shim: quarantine/ and public/ under a base dir."""

    def __init__(self, base_dir: str, public_base_url: str) -> None:
        self._root = Path(base_dir)
        self._public_base_url = public_base_url.rstrip("/")
        (self._root / "quarantine").mkdir(parents=True, exist_ok=True)
        (self._root / "public").mkdir(parents=True, exist_ok=True)

    def _write(self, area: str, data: bytes, content_type: str) -> StoredObject:
        key = _new_key(area, content_type)
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(key=key, content_type=content_type, size=len(data))

    def put_quarantine(self, *, data: bytes, content_type: str) -> StoredObject:
        return self._write("quarantine", data, content_type)

    def put_public(self, *, data: bytes, content_type: str) -> StoredObject:
        return self._write("public", data, content_type)

    def read(self, key: str) -> bytes:
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents:
            raise StorageError("invalid storage key")
        if not path.is_file():
            raise StorageError(f"missing object: {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents:
            raise StorageError("invalid storage key")
        path.unlink(missing_ok=True)

    def public_url(self, key: str) -> str:
        if not key.startswith("public/"):
            raise StorageError("only public objects have a public URL")
        return f"{self._public_base_url}/{key[len('public/') :]}"

    def presign_put(self, *, content_type: str) -> dict:
        # Local dev has no presigned POST; caller uploads via the API instead.
        raise StorageError("presigned upload requires the s3 backend (Phase 7)")


class S3Storage:  # pragma: no cover - wired in Phase 7 hardening
    def __init__(self, *_: object, **__: object) -> None:
        raise NotImplementedError("S3/R2 backend lands in Phase 7 (ADR-005)")

    def put_quarantine(self, *, data: bytes, content_type: str) -> StoredObject:
        raise NotImplementedError

    def put_public(self, *, data: bytes, content_type: str) -> StoredObject:
        raise NotImplementedError

    def read(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def public_url(self, key: str) -> str:
        raise NotImplementedError

    def presign_put(self, *, content_type: str) -> dict:
        raise NotImplementedError


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    settings = get_settings()
    if settings.evidence_storage_backend == "s3":  # pragma: no cover
        return S3Storage()
    return LocalStorage(settings.evidence_local_dir, settings.evidence_public_base_url)
