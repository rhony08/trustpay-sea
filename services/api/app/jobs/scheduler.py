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
    from app.db import SessionLocal
    from app.services.search_intel import rollup_search_stats

    async with SessionLocal() as db:
        count = await rollup_search_stats(db)
    log.info("search_stats_rollup: recomputed %d entit(ies)", count)


async def anti_brigading_scan_job() -> None:
    """Identity-graph velocity scan → ANOMALY_SPIKE_DETECTED (Phase 6)."""
    log.info("anti_brigading_scan: placeholder run (detector lands in Phase 6)")


async def audit_chain_reconcile_job() -> None:
    """Nightly hash-chain integrity check over audit_logs (§9.3 SLO)."""
    log.info("audit_chain_reconcile: placeholder run (reconciler lands in Phase 7)")


async def report_processing_job() -> None:
    """Publish any reports left PROCESSING (Phase 2.3 async worker safety-net)."""
    from app.config import get_settings
    from app.db import SessionLocal
    from app.workers.report_pipeline import process_pending_reports

    if not get_settings().report_worker_interval_seconds:
        return
    async with SessionLocal() as db:
        published = await process_pending_reports(db)
    if published:
        log.info("report_processing: published %d report(s)", published)


def start_scheduler() -> None:
    if scheduler.running:
        return
    from app.config import get_settings

    settings = get_settings()
    scheduler.add_job(
        report_processing_job,
        "interval",
        seconds=settings.report_worker_interval_seconds,
        id="report_processing",
        replace_existing=True,
    )
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
