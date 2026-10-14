"""PDRM Semak Mule adapter — Malaysia government mule-account checker.

Endpoint: POST {SEMAKMULE_BASE_URL} with header `apikey` and body
``{"data": {"category": "bank", "bankAccount": "<acct>", ...}}``.

Observed response (2026-10):
``{"status":1,"status_message":"Success.","table_header":["No. Akaun","Repot"],
   "table_data":[["123123123",1]],"count":39,"cat":1,"kw":"123123123"}``
where each ``table_data`` row is ``[value, report_count]``.

The checker is **disabled unless `SEMAKMULE_API_KEY` is set**. Network/TLS
failures degrade to ``available=False`` (we never report a failed check as
"clean"). The key is env-only and never logged.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import httpx

from app.config import Settings, get_settings

log = logging.getLogger("trustpay.gov.semakmule")

SOURCE = "semakmule.rmp.gov.my"
_CATEGORY_FIELD = {"bank": "bankAccount", "phone": "telNo", "company": "companyName"}
_MY_PHONE_RE = re.compile(r"^(\+?60|0)\d{7,10}$")


def looks_like_phone(value: str) -> bool:
    return bool(_MY_PHONE_RE.match(re.sub(r"[^\d+]", "", value or "")))


def infer_category(*, bank_type: str | None, value: str) -> str:
    """E-wallets and phone-shaped identifiers use the Semak Mule *telefon* checker."""
    if (bank_type or "").upper() == "E_WALLET":
        return "phone"
    return "phone" if looks_like_phone(value) else "bank"


@dataclass
class GovCheckResult:
    source: str = SOURCE
    available: bool = False
    found: bool = False
    report_count: int = 0
    reports: list[dict[str, Any]] = field(default_factory=list)
    status_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "available": self.available,
            "found": self.found,
            "report_count": self.report_count,
            "reports": self.reports,
            "status_message": self.status_message,
        }


def parse_response(payload: Any) -> GovCheckResult:
    if not isinstance(payload, dict):
        return GovCheckResult(available=True, status_message="unexpected response")
    reports: list[dict[str, Any]] = []
    for row in payload.get("table_data") or []:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            try:
                count = int(row[1])
            except (TypeError, ValueError):
                count = 0
            reports.append({"value": str(row[0]), "report_count": count})
        elif isinstance(row, dict):
            count = row.get("Repot") or row.get("report_count") or 0
            try:
                count = int(count)
            except (TypeError, ValueError):
                count = 0
            reports.append(
                {"value": str(row.get("value") or row.get("No. Akaun")), "report_count": count}
            )

    found = any(item["report_count"] > 0 for item in reports)
    report_count = sum(item["report_count"] for item in reports)
    return GovCheckResult(
        available=True,
        found=found,
        report_count=report_count,
        reports=reports,
        status_message=payload.get("status_message"),
    )


class SemakMuleClient:
    source = SOURCE

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._http = http

    @property
    def enabled(self) -> bool:
        return bool(self._settings.semakmule_api_key)

    async def _post(self, body: dict) -> dict:
        headers = {
            "apikey": self._settings.semakmule_api_key or "",
            "Content-Type": "application/json",
        }
        owned = self._http is None
        client = self._http or httpx.AsyncClient(
            timeout=self._settings.semakmule_timeout_seconds,
            verify=self._settings.semakmule_verify_tls,
        )
        try:
            resp = await client.post(self._settings.semakmule_base_url, json=body, headers=headers)
            resp.raise_for_status()
            return resp.json()
        finally:
            if owned:
                await client.aclose()

    async def check(self, *, category: str, value: str) -> GovCheckResult:
        if not self.enabled or not value:
            return GovCheckResult(available=False)
        field = _CATEGORY_FIELD.get(category, "bankAccount")
        body = {
            "data": {
                "category": category,
                "bankAccount": "",
                "telNo": "",
                "companyName": "",
                "captcha": "",
            }
        }
        body["data"][field] = value
        try:
            payload = await self._post(body)
        except Exception as exc:  # noqa: BLE001 — degrade, never claim "clean"
            log.warning("semakmule check failed: %s", type(exc).__name__)
            return GovCheckResult(available=False)
        return parse_response(payload)

    async def check_bank(self, account: str) -> GovCheckResult:
        return await self.check(category="bank", value=account)

    async def check_phone(self, tel: str) -> GovCheckResult:
        return await self.check(category="phone", value=tel)

    async def check_company(self, name: str) -> GovCheckResult:
        return await self.check(category="company", value=name)


@lru_cache(maxsize=1)
def get_semakmule_client() -> SemakMuleClient:
    return SemakMuleClient(get_settings())


def reset_semakmule_client() -> None:
    get_semakmule_client.cache_clear()
