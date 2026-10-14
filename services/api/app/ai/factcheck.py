"""Google Fact Check Tools enrichment (Phase 3.5) — keyless-safe.

Without `FACTCHECK_API_KEY` this returns `[]` and never crashes (mock-first,
ADR-012). With a key it queries the public claims:search endpoint and degrades
to `[]` on any error so enrichment can never break a lookup.
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

log = logging.getLogger("trustpay.factcheck")

_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


async def lookup_fact_checks(query: str, *, max_results: int = 3) -> list[dict]:
    settings = get_settings()
    if not settings.factcheck_api_key or not query.strip():
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                _ENDPOINT,
                params={"query": query, "key": settings.factcheck_api_key, "pageSize": max_results},
            )
            if resp.status_code != 200:
                return []
            claims = resp.json().get("claims", [])
    except httpx.HTTPError as exc:  # graceful degradation
        log.warning("fact-check lookup failed: %s", exc)
        return []
    return [
        {
            "text": claim.get("text"),
            "claimant": claim.get("claimant"),
            "rating": (claim.get("claimReview") or [{}])[0].get("textualRating"),
            "url": (claim.get("claimReview") or [{}])[0].get("url"),
        }
        for claim in claims[:max_results]
    ]
