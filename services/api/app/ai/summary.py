"""Grounded AI entity summary (Phase 3.4).

Prompt-injection-proof **by construction**: the summary is assembled server-side
from validated structured fields only — untrusted report/OCR/merchant text is
never interpolated. A `grounding_check` asserts every number in the output is
traceable to the input facts, so an LLM swap-in cannot silently hallucinate.
"""

from __future__ import annotations

import re

_NUMBER_RE = re.compile(r"\d+")


def build_entity_summary(facts: dict) -> str:
    label = facts.get("entity_label") or facts.get("entity_type") or "This entity"
    total = int(facts.get("total_reports") or 0)
    verified = int(facts.get("admin_verified_reports") or 0)

    parts: list[str] = []
    if total == 0:
        parts.append(f"No community fraud reports have been filed for {label} yet.")
    else:
        sentence = f"{label} has received {total} community fraud report(s)"
        if facts.get("first_reported_at"):
            sentence += f" since {str(facts['first_reported_at'])[:10]}"
        parts.append(sentence + ".")

    if verified:
        parts.append(f"{verified} of them have been admin-verified.")
    if facts.get("is_gov_blacklisted"):
        parts.append("It appears on a government fraud blacklist.")
    if facts.get("is_under_dispute"):
        parts.append("An ownership dispute is active.")
    if facts.get("report_velocity_7d"):
        parts.append(
            f"{int(facts['report_velocity_7d'])} new report(s) arrived over the past week."
        )
    if verified == 0 and total > 0:
        parts.append("No admin-verified fraud has been recorded.")
    return " ".join(parts)


def _allowed_numbers(facts: dict) -> set[str]:
    allowed: set[str] = set()
    for value in facts.values():
        if isinstance(value, int):
            allowed.add(str(value))
        elif isinstance(value, str):
            allowed.update(_NUMBER_RE.findall(value))
    return allowed


def summary_is_grounded(summary: str, facts: dict) -> bool:
    """Every number in the summary must be present in the input facts."""
    allowed = _allowed_numbers(facts)
    return all(number in allowed for number in _NUMBER_RE.findall(summary))
