"""
APScheduler-based background job scheduler.

Configures recurring jobs for different endpoint categories at
appropriate intervals — from 30-second live polls to weekly
historical syncs.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.utils import get_logger

if TYPE_CHECKING:
    from app.sportmonks_service import SportmonksClient

logger = get_logger("f1_pipeline.scheduler")

# ── Module-level state ──────────────────────────────────────────────
_scheduler: AsyncIOScheduler | None = None
_client: SportmonksClient | None = None


# ── Job functions ───────────────────────────────────────────────────

async def _sync_live() -> None:
    """Job: sync live endpoints (every 30 seconds)."""
    if _client is None:
        return
    try:
        results = await _client.sync_live()
        logger.info("scheduler_job_completed", job="live", results=results)
    except Exception as exc:
        logger.error("scheduler_job_failed", job="live", error=str(exc))


async def _sync_standings() -> None:
    """Job: sync standings (every 30 minutes)."""
    if _client is None:
        return
    try:
        results = await _client.sync_category("standings")
        logger.info("scheduler_job_completed", job="standings", results=results)
    except Exception as exc:
        logger.error("scheduler_job_failed", job="standings", error=str(exc))


async def _sync_frequent() -> None:
    """Job: sync fixtures and stages (every 6 hours)."""
    if _client is None:
        return
    try:
        results = await _client.sync_category("frequent")
        logger.info("scheduler_job_completed", job="frequent", results=results)
    except Exception as exc:
        logger.error("scheduler_job_failed", job="frequent", error=str(exc))


async def _sync_daily() -> None:
    """Job: sync drivers and teams (once per day)."""
    if _client is None:
        return
    try:
        results = await _client.sync_category("daily")
        logger.info("scheduler_job_completed", job="daily", results=results)
    except Exception as exc:
        logger.error("scheduler_job_failed", job="daily", error=str(exc))


async def _sync_historical() -> None:
    """Job: sync seasons, venues, countries, leagues (once per week)."""
    if _client is None:
        return
    try:
        results = await _client.sync_category("historical")
        logger.info("scheduler_job_completed", job="historical", results=results)
    except Exception as exc:
        logger.error("scheduler_job_failed", job="historical", error=str(exc))


async def _sync_deep() -> None:
    """Job: sync laps, pitstops, stints (once per week)."""
    if _client is None:
        return
    try:
        results = await _client.sync_category("deep")
        logger.info("scheduler_job_completed", job="deep", results=results)
    except Exception as exc:
        logger.error("scheduler_job_failed", job="deep", error=str(exc))


# ── Scheduler lifecycle ─────────────────────────────────────────────

def init_scheduler(client: SportmonksClient) -> AsyncIOScheduler:
    """
    Create and configure the APScheduler with all recurring jobs.

    Call ``scheduler.start()`` after this to begin execution.
    """
    global _scheduler, _client
    _client = client

    _scheduler = AsyncIOScheduler(
        job_defaults={
            "coalesce": True,            # skip missed runs, run once when back
            "max_instances": 1,          # prevent overlapping runs
            "misfire_grace_time": 60,    # seconds
        }
    )

    # ── Live (every 30 seconds) ──
    _scheduler.add_job(
        _sync_live,
        trigger=IntervalTrigger(seconds=30),
        id="sync_live",
        name="Sync live data",
        replace_existing=True,
    )

    # ── Standings (every 30 minutes) ──
    _scheduler.add_job(
        _sync_standings,
        trigger=IntervalTrigger(minutes=30),
        id="sync_standings",
        name="Sync standings",
        replace_existing=True,
    )

    # ── Fixtures / stages (every 6 hours) ──
    _scheduler.add_job(
        _sync_frequent,
        trigger=IntervalTrigger(hours=6),
        id="sync_frequent",
        name="Sync fixtures & stages",
        replace_existing=True,
    )

    # ── Drivers & teams (once per day) ──
    _scheduler.add_job(
        _sync_daily,
        trigger=IntervalTrigger(days=1),
        id="sync_daily",
        name="Sync drivers & teams",
        replace_existing=True,
    )

    # ── Historical (once per week) ──
    _scheduler.add_job(
        _sync_historical,
        trigger=IntervalTrigger(weeks=1),
        id="sync_historical",
        name="Sync historical data",
        replace_existing=True,
    )

    # ── Deep data (once per week) ──
    _scheduler.add_job(
        _sync_deep,
        trigger=IntervalTrigger(weeks=1),
        id="sync_deep",
        name="Sync deep data (laps, pitstops, stints)",
        replace_existing=True,
    )

    logger.info("Scheduler configured with %d jobs", len(_scheduler.get_jobs()))
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler (non-blocking — runs on the asyncio event loop)."""
    if _scheduler is not None and not _scheduler.running:
        _scheduler.start()
        logger.info("Scheduler started")


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")


def get_scheduler_status() -> list[dict[str, str]]:
    """Return the current status of all scheduled jobs."""
    if _scheduler is None:
        return []

    jobs = []
    for job in _scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else "paused",
            "trigger": str(job.trigger),
        })
    return jobs
