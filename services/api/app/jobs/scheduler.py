"""Placeholder cron jobs (Phase 0.5) — APScheduler in-process.

Real rollup/anti-brigading logic lands in Phases 3 and 6; these jobs exist so
the scheduling infrastructure is verifiable from day one (acceptance criteria:
"clock job exists & runs on schedule").
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

log = logging.getLogger("trustpay.jobs")

scheduler = AsyncIOScheduler(timezone="UTC")


async def search_stats_rollup_job() -> None:
    """Roll search_events_daily → entity_search_stats 7d/30d/total windows (Phase 3)."""
    log.info("search_stats_rollup: placeholder run (rollup lands in Phase 3)")


async def anti_brigading_scan_job() -> None:
    """Identity-graph velocity scan → ANOMALY_SPIKE_DETECTED (Phase 6)."""
    log.info("anti_brigading_scan: placeholder run (detector lands in Phase 6)")


async def audit_chain_reconcile_job() -> None:
    """Nightly hash-chain integrity check over audit_logs (§9.3 SLO)."""
    log.info("audit_chain_reconcile: placeholder run (reconciler lands in Phase 7)")


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        search_stats_rollup_job,
        "cron",
        hour=1,
        minute=0,
        id="search_stats_rollup",
        replace_existing=True,
    )
    scheduler.add_job(
        anti_brigading_scan_job,
        "interval",
        minutes=60,
        id="anti_brigading_scan",
        replace_existing=True,
    )
    scheduler.add_job(
        audit_chain_reconcile_job,
        "cron",
        hour=3,
        minute=0,
        id="audit_chain_reconcile",
        replace_existing=True,
    )
    scheduler.start()
    log.info("scheduler started: %s jobs", len(scheduler.get_jobs()))


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler stopped")
