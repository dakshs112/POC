"""
FastAPI routes — sync triggers (POST) and data query endpoints (GET).

All sync endpoints dispatch work as background tasks and return
immediately.  All query endpoints support pagination and optional
filtering.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from math import ceil
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app import analytics
from app.database import get_collection, get_database
from app.scheduler import get_scheduler_status
from app.sportmonks_service import SportmonksClient
from app.utils import get_logger

logger = get_logger("f1_pipeline.routes")

router = APIRouter()

# ── Dependency: Sportmonks client (set during lifespan) ─────────────
_sportmonks_client: SportmonksClient | None = None


def set_sportmonks_client(client: SportmonksClient) -> None:
    """Called by main.py lifespan to wire up the singleton client."""
    global _sportmonks_client
    _sportmonks_client = client


def get_client() -> SportmonksClient:
    """FastAPI dependency returning the active SportmonksClient."""
    if _sportmonks_client is None:
        raise RuntimeError("SportmonksClient not initialised")
    return _sportmonks_client


def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency returning the active Motor database."""
    return get_database()


# ══════════════════════════════════════════════════════════════════════
#  HEALTH & STATUS
# ══════════════════════════════════════════════════════════════════════

@router.get("/health", tags=["Health"])
async def health_check(db: AsyncIOMotorDatabase = Depends(get_db)) -> dict[str, Any]:
    """Application health check — pings MongoDB."""
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
    }


@router.get("/scheduler/status", tags=["Health"])
async def scheduler_status() -> dict[str, Any]:
    """Return the status of all scheduled background jobs."""
    return {"jobs": get_scheduler_status()}


# ══════════════════════════════════════════════════════════════════════
#  SYNC TRIGGERS (POST)
# ══════════════════════════════════════════════════════════════════════

def _sync_response(task_id: str, description: str) -> dict[str, str]:
    return {
        "status": "sync_started",
        "task_id": task_id,
        "description": description,
    }


@router.post("/sync/all", tags=["Sync"])
async def sync_all(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Trigger a full pipeline sync across all endpoints."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_all)
    logger.info("sync_triggered", task_id=task_id, scope="all")
    return _sync_response(task_id, "Full pipeline sync started")


@router.post("/sync/drivers", tags=["Sync"])
async def sync_drivers(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync drivers."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_collection, "drivers")
    logger.info("sync_triggered", task_id=task_id, scope="drivers")
    return _sync_response(task_id, "Drivers sync started")


@router.post("/sync/teams", tags=["Sync"])
async def sync_teams(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync teams."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_collection, "teams")
    logger.info("sync_triggered", task_id=task_id, scope="teams")
    return _sync_response(task_id, "Teams sync started")


@router.post("/sync/races", tags=["Sync"])
async def sync_races(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync fixtures (races) and stages."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_category, "frequent")
    logger.info("sync_triggered", task_id=task_id, scope="races")
    return _sync_response(task_id, "Races / fixtures sync started")


@router.post("/sync/standings", tags=["Sync"])
async def sync_standings(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync driver and team standings."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_category, "standings")
    logger.info("sync_triggered", task_id=task_id, scope="standings")
    return _sync_response(task_id, "Standings sync started")


@router.post("/sync/live", tags=["Sync"])
async def sync_live(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync live race data."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_live)
    logger.info("sync_triggered", task_id=task_id, scope="live")
    return _sync_response(task_id, "Live data sync started")


@router.post("/sync/seasons", tags=["Sync"])
async def sync_seasons(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync seasons."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_collection, "seasons")
    logger.info("sync_triggered", task_id=task_id, scope="seasons")
    return _sync_response(task_id, "Seasons sync started")


@router.post("/sync/venues", tags=["Sync"])
async def sync_venues(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync venues / circuits."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_collection, "venues")
    logger.info("sync_triggered", task_id=task_id, scope="venues")
    return _sync_response(task_id, "Venues sync started")


@router.post("/sync/laps", tags=["Sync"])
async def sync_laps(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync lap data for all fixtures."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_collection, "laps")
    logger.info("sync_triggered", task_id=task_id, scope="laps")
    return _sync_response(task_id, "Laps sync started")


@router.post("/sync/pitstops", tags=["Sync"])
async def sync_pitstops(
    background_tasks: BackgroundTasks,
    client: SportmonksClient = Depends(get_client),
) -> dict[str, str]:
    """Sync pit-stop data for all fixtures."""
    task_id = str(uuid.uuid4())
    background_tasks.add_task(client.sync_collection, "pitstops")
    logger.info("sync_triggered", task_id=task_id, scope="pitstops")
    return _sync_response(task_id, "Pitstops sync started")


# ══════════════════════════════════════════════════════════════════════
#  QUERY ENDPOINTS (GET) — Pagination & Filtering
# ══════════════════════════════════════════════════════════════════════

async def _paginated_query(
    collection_name: str,
    db: AsyncIOMotorDatabase,
    page: int = 1,
    per_page: int = 25,
    filters: dict[str, Any] | None = None,
    search: str | None = None,
    search_fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generic paginated MongoDB query with optional filters and text search.

    Returns:
        {
            "data": [...],
            "pagination": { "page", "per_page", "total", "total_pages" }
        }
    """
    coll = db[collection_name]
    query: dict[str, Any] = {}

    # Apply explicit filters
    if filters:
        for key, value in filters.items():
            if value is not None:
                query[key] = value

    # Simple regex search across specified fields
    if search and search_fields:
        or_clauses = [
            {field: {"$regex": search, "$options": "i"}}
            for field in search_fields
        ]
        query["$or"] = or_clauses

    total = await coll.count_documents(query)
    total_pages = max(1, ceil(total / per_page))
    skip = (page - 1) * per_page

    cursor = coll.find(query, {"_id": 0}).skip(skip).limit(per_page).sort("sportmonks_id", 1)
    data = await cursor.to_list(length=per_page)

    return {
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }


# ── Drivers ─────────────────────────────────────────────────────────

@router.get("/drivers", tags=["Data"])
async def list_drivers(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    season_id: int | None = Query(None),
    team_id: int | None = Query(None),
    search: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List all drivers with pagination and optional filters."""
    filters: dict[str, Any] = {}
    if season_id is not None:
        filters["normalized.season_id"] = season_id
    if team_id is not None:
        filters["normalized.team_id"] = team_id

    return await _paginated_query(
        "drivers", db, page, per_page, filters, search,
        search_fields=["normalized.name", "normalized.display_name", "normalized.first_name", "normalized.last_name"],
    )


@router.get("/drivers/{sportmonks_id}", tags=["Data"])
async def get_driver(
    sportmonks_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get a single driver by Sportmonks ID."""
    doc = await db["drivers"].find_one({"sportmonks_id": sportmonks_id}, {"_id": 0})
    if doc is None:
        return {"error": "Driver not found", "sportmonks_id": sportmonks_id}
    return {"data": doc}


# ── Teams ───────────────────────────────────────────────────────────

@router.get("/teams", tags=["Data"])
async def list_teams(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    season_id: int | None = Query(None),
    search: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List all teams / constructors."""
    filters: dict[str, Any] = {}
    if season_id is not None:
        filters["normalized.season_id"] = season_id

    return await _paginated_query(
        "teams", db, page, per_page, filters, search,
        search_fields=["normalized.name", "normalized.short_code"],
    )


@router.get("/teams/{sportmonks_id}", tags=["Data"])
async def get_team(
    sportmonks_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get a single team by Sportmonks ID."""
    doc = await db["teams"].find_one({"sportmonks_id": sportmonks_id}, {"_id": 0})
    if doc is None:
        return {"error": "Team not found", "sportmonks_id": sportmonks_id}
    return {"data": doc}


# ── Races (fixtures) ───────────────────────────────────────────────

@router.get("/races", tags=["Data"])
async def list_races(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    season_id: int | None = Query(None),
    venue_id: int | None = Query(None),
    search: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List all races / fixtures."""
    filters: dict[str, Any] = {}
    if season_id is not None:
        filters["normalized.season_id"] = season_id
    if venue_id is not None:
        filters["normalized.venue_id"] = venue_id

    return await _paginated_query(
        "fixtures", db, page, per_page, filters, search,
        search_fields=["normalized.name"],
    )


@router.get("/races/{sportmonks_id}", tags=["Data"])
async def get_race(
    sportmonks_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Get a single race / fixture by Sportmonks ID."""
    doc = await db["fixtures"].find_one({"sportmonks_id": sportmonks_id}, {"_id": 0})
    if doc is None:
        return {"error": "Race not found", "sportmonks_id": sportmonks_id}
    return {"data": doc}


# ── Standings ───────────────────────────────────────────────────────

@router.get("/standings", tags=["Data"])
async def list_standings(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    season_id: int | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List all standings (driver + team combined)."""
    filters: dict[str, Any] = {}
    if season_id is not None:
        filters["normalized.season_id"] = season_id

    # Combine driver and team standings
    driver_data = await _paginated_query("driver_standings", db, page, per_page, filters)
    team_data = await _paginated_query("team_standings", db, page, per_page, filters)

    return {
        "driver_standings": driver_data,
        "team_standings": team_data,
    }


@router.get("/standings/drivers", tags=["Data"])
async def list_driver_standings(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    season_id: int | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List driver championship standings."""
    filters: dict[str, Any] = {}
    if season_id is not None:
        filters["normalized.season_id"] = season_id
    return await _paginated_query("driver_standings", db, page, per_page, filters)


@router.get("/standings/teams", tags=["Data"])
async def list_team_standings(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    season_id: int | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List team / constructor championship standings."""
    filters: dict[str, Any] = {}
    if season_id is not None:
        filters["normalized.season_id"] = season_id
    return await _paginated_query("team_standings", db, page, per_page, filters)


# ── Results ─────────────────────────────────────────────────────────

@router.get("/results", tags=["Data"])
async def list_results(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    season_id: int | None = Query(None),
    fixture_id: int | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List race results (from fixtures with result_info)."""
    filters: dict[str, Any] = {"normalized.result_info": {"$ne": None}}
    if season_id is not None:
        filters["normalized.season_id"] = season_id
    if fixture_id is not None:
        filters["sportmonks_id"] = fixture_id
    return await _paginated_query("fixtures", db, page, per_page, filters)


# ── Seasons ─────────────────────────────────────────────────────────

@router.get("/seasons", tags=["Data"])
async def list_seasons(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List all seasons."""
    return await _paginated_query(
        "seasons", db, page, per_page, search=search,
        search_fields=["normalized.name"],
    )


# ── Venues ──────────────────────────────────────────────────────────

@router.get("/venues", tags=["Data"])
async def list_venues(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List all venues / circuits."""
    return await _paginated_query(
        "venues", db, page, per_page, search=search,
        search_fields=["normalized.name", "normalized.city"],
    )


# ── Laps ────────────────────────────────────────────────────────────

@router.get("/laps", tags=["Data"])
async def list_laps(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    fixture_id: int | None = Query(None),
    driver_id: int | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """List lap data with optional fixture / driver filters."""
    filters: dict[str, Any] = {}
    if fixture_id is not None:
        filters["normalized.fixture_id"] = fixture_id
    if driver_id is not None:
        filters["normalized.driver_id"] = driver_id
    return await _paginated_query("laps", db, page, per_page, filters)


# ── Statistics ──────────────────────────────────────────────────────

@router.get("/statistics", tags=["Analytics"])
async def get_statistics(
    season_id: int | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Return aggregated overview statistics."""
    return await analytics.get_overview_statistics(db, season_id=season_id)


@router.get("/statistics/drivers", tags=["Analytics"])
async def get_driver_stats(
    season_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Return aggregated driver statistics."""
    data = await analytics.get_driver_statistics(db, season_id=season_id, limit=limit)
    return {"data": data}


@router.get("/statistics/teams", tags=["Analytics"])
async def get_team_stats(
    season_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Return aggregated team / constructor statistics."""
    data = await analytics.get_team_statistics(db, season_id=season_id, limit=limit)
    return {"data": data}


@router.get("/statistics/seasons", tags=["Analytics"])
async def get_season_stats(
    season_id: int | None = Query(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Return per-season summaries."""
    data = await analytics.get_season_summary(db, season_id=season_id)
    return {"data": data}


@router.get("/statistics/venues", tags=["Analytics"])
async def get_venue_stats(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Return venue / circuit usage statistics."""
    data = await analytics.get_venue_statistics(db, limit=limit)
    return {"data": data}


@router.get("/statistics/pitstops", tags=["Analytics"])
async def get_pitstop_stats(
    fixture_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Return pit-stop analytics."""
    data = await analytics.get_pitstop_analytics(db, fixture_id=fixture_id, limit=limit)
    return {"data": data}


@router.get("/statistics/laps", tags=["Analytics"])
async def get_lap_stats(
    fixture_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict[str, Any]:
    """Return lap analytics (fastest laps)."""
    data = await analytics.get_lap_analytics(db, fixture_id=fixture_id, limit=limit)
    return {"data": data}
