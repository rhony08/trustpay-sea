"""Test-account seeder: one login per role for end-to-end role testing.

Idempotent: creates accounts that don't exist and resets role/password for the
known test emails, so it's safe to re-run. Prints the credential table.

    python -m app.seeds.seed_test_accounts

NOTE: on a prod instance with MFA_REQUIRED_FOR_ADMINS=true, admin roles cannot
log in until a passkey is enrolled (ADR-020). For testing, set
MFA_REQUIRED_FOR_ADMINS=false, or enroll a passkey from /profile after login.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.security import hash_password
from app.enums import Role
from app.models import User

log = logging.getLogger("trustpay.seed.test_accounts")

PASSWORD = "demo-analyst-pass"

# email, display name, role
ACCOUNTS: list[tuple[str, str, Role]] = [
    ("user@trustpay.dev", "Demo User", Role.USER),
    ("merchant@trustpay.dev", "Demo Merchant (owner flows)", Role.USER),
    ("analyst@trustpay.dev", "Demo Analyst", Role.ANALYST),
    ("senior@trustpay.dev", "Demo Senior Analyst", Role.SENIOR_ANALYST),
    ("superadmin@trustpay.dev", "Demo Superadmin", Role.SUPERADMIN),
]


async def seed_test_accounts(db) -> dict:
    created: list[str] = []
    updated: list[str] = []
    for email, name, role in ACCOUNTS:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            db.add(
                User(
                    email=email,
                    display_name=name,
                    password_hash=hash_password(PASSWORD),
                    role=role.value,
                )
            )
            created.append(email)
        else:
            user.role = role.value
            user.password_hash = hash_password(PASSWORD)
            if not user.display_name:
                user.display_name = name
            updated.append(email)
    await db.commit()
    return {
        "created": created,
        "updated": updated,
        "password": PASSWORD,
        "accounts": [{"email": e, "role": r.value} for e, _, r in ACCOUNTS],
    }


async def _main() -> None:
    from app.db import SessionLocal, engine

    async with SessionLocal() as db:
        result = await seed_test_accounts(db)
    await engine.dispose()
    print("seed_test_accounts:", result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_main())
