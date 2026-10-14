"""Health + demo RBAC endpoints."""

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.deps import require_role
from app.enums import Role
from app.models import User

router = APIRouter(tags=["system"])


@router.get("/healthz")
async def healthz():
    settings = get_settings()
    return {"status": "ok", "version": settings.version}


@router.get("/protected-ping")
async def protected_ping(user: User = Depends(require_role(Role.ANALYST))):
    """RBAC demo: only ANALYST+ may call. Used by Phase 0 acceptance tests."""
    return {"status": "ok", "role": user.role}
