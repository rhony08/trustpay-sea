"""Government fraud-registry adapter (Phase 6.3) — mock feed.

Production swaps in real connectors (cekrekening.id first, per R-4). The mock
feed maps an account hash → source name so a entity can be flagged
`GOV_BLACKLISTED`, which forces score 100 with public source attribution.
"""

from __future__ import annotations

_MOCK_FEED: dict[str, str] = {}


def add_mock_entry(account_hash: str, source: str) -> None:
    _MOCK_FEED[account_hash] = source


def clear_mock_feed() -> None:
    _MOCK_FEED.clear()


def lookup(account_hash: str) -> str | None:
    return _MOCK_FEED.get(account_hash)
