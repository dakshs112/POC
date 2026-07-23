"""
Analytics module — MongoDB aggregation pipelines for F1 insights.

All functions accept the Motor database handle and return dicts /
lists ready to be serialised as JSON.
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.utils import get_logger

logger = get_logger("f1_pipeline.analytics")


# ── Driver statistics ───────────────────────────────────────────────

async def get_driver_statistics(
    db: AsyncIOMotorDatabase,
    season_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Aggregate driver statistics from standings.

    Returns top drivers sorted by total points descending.
    """
    match_stage: dict[str, Any] = {}
    if season_id is not None:
        match_stage["normalized.season_id"] = season_id

    pipeline: list[dict[str, Any]] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$group": {
                "_id": "$normalized.participant_id",
                "total_points": {"$sum": {"$ifNull": ["$normalized.points", 0]}},
                "seasons_competed": {"$addToSet": "$normalized.season_id"},
                "best_position": {"$min": "$normalized.position"},
                "entries": {"$sum": 1},
            }
        },
        {"$sort": {"total_points": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "participant_id": "$_id",
                "total_points": 1,
                "seasons_competed": {"$size": "$seasons_competed"},
                "best_position": 1,
                "entries": 1,
            }
        },
    ])

    return await db["driver_standings"].aggregate(pipeline).to_list(length=limit)


# ── Team / constructor statistics ───────────────────────────────────

async def get_team_statistics(
    db: AsyncIOMotorDatabase,
    season_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Aggregate constructor statistics from team standings.

    Returns teams sorted by total points descending.
    """
    match_stage: dict[str, Any] = {}
    if season_id is not None:
        match_stage["normalized.season_id"] = season_id

    pipeline: list[dict[str, Any]] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$group": {
                "_id": "$normalized.participant_id",
                "total_points": {"$sum": {"$ifNull": ["$normalized.points", 0]}},
                "seasons_competed": {"$addToSet": "$normalized.season_id"},
                "best_position": {"$min": "$normalized.position"},
                "entries": {"$sum": 1},
            }
        },
        {"$sort": {"total_points": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "participant_id": "$_id",
                "total_points": 1,
                "seasons_competed": {"$size": "$seasons_competed"},
                "best_position": 1,
                "entries": 1,
            }
        },
    ])

    return await db["team_standings"].aggregate(pipeline).to_list(length=limit)


# ── Season summaries ────────────────────────────────────────────────

async def get_season_summary(
    db: AsyncIOMotorDatabase,
    season_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Per-season summary: total fixtures, unique stages, unique venues.
    """
    match_stage: dict[str, Any] = {}
    if season_id is not None:
        match_stage["normalized.season_id"] = season_id

    pipeline: list[dict[str, Any]] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$group": {
                "_id": "$normalized.season_id",
                "total_fixtures": {"$sum": 1},
                "unique_stages": {"$addToSet": "$normalized.stage_id"},
                "unique_venues": {"$addToSet": "$normalized.venue_id"},
                "fixture_types": {"$addToSet": "$normalized.type"},
            }
        },
        {"$sort": {"_id": -1}},
        {
            "$project": {
                "_id": 0,
                "season_id": "$_id",
                "total_fixtures": 1,
                "unique_stages": {"$size": "$unique_stages"},
                "unique_venues": {"$size": "$unique_venues"},
                "fixture_types": 1,
            }
        },
    ])

    return await db["fixtures"].aggregate(pipeline).to_list(length=100)


# ── Venue statistics ────────────────────────────────────────────────

async def get_venue_statistics(
    db: AsyncIOMotorDatabase,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """How many races/fixtures have been held at each venue."""

    pipeline = [
        {"$match": {"normalized.venue_id": {"$ne": None}}},
        {
            "$group": {
                "_id": "$normalized.venue_id",
                "total_fixtures": {"$sum": 1},
                "seasons": {"$addToSet": "$normalized.season_id"},
            }
        },
        {"$sort": {"total_fixtures": -1}},
        {"$limit": limit},
        {
            "$project": {
                "_id": 0,
                "venue_id": "$_id",
                "total_fixtures": 1,
                "seasons_count": {"$size": "$seasons"},
            }
        },
    ]

    return await db["fixtures"].aggregate(pipeline).to_list(length=limit)


# ── Pit-stop analytics ─────────────────────────────────────────────

async def get_pitstop_analytics(
    db: AsyncIOMotorDatabase,
    fixture_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Average pit-stop count per fixture (or for a single fixture)."""

    match_stage: dict[str, Any] = {}
    if fixture_id is not None:
        match_stage["normalized.fixture_id"] = fixture_id

    pipeline: list[dict[str, Any]] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$group": {
                "_id": "$normalized.fixture_id",
                "total_pitstops": {"$sum": 1},
                "unique_drivers": {"$addToSet": "$normalized.driver_id"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "fixture_id": "$_id",
                "total_pitstops": 1,
                "unique_drivers": {"$size": "$unique_drivers"},
                "avg_per_driver": {
                    "$cond": {
                        "if": {"$gt": [{"$size": "$unique_drivers"}, 0]},
                        "then": {"$divide": ["$total_pitstops", {"$size": "$unique_drivers"}]},
                        "else": 0,
                    }
                },
            }
        },
        {"$sort": {"total_pitstops": -1}},
        {"$limit": limit},
    ])

    return await db["pitstops"].aggregate(pipeline).to_list(length=limit)


# ── Lap analytics ───────────────────────────────────────────────────

async def get_lap_analytics(
    db: AsyncIOMotorDatabase,
    fixture_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fastest laps and lap statistics per fixture."""

    match_stage: dict[str, Any] = {"normalized.is_fastest": True}
    if fixture_id is not None:
        match_stage["normalized.fixture_id"] = fixture_id

    pipeline: list[dict[str, Any]] = [
        {"$match": match_stage},
        {
            "$project": {
                "_id": 0,
                "fixture_id": "$normalized.fixture_id",
                "driver_id": "$normalized.driver_id",
                "participant_id": "$normalized.participant_id",
                "lap_number": "$normalized.lap_number",
                "time": "$normalized.time",
                "position": "$normalized.position",
            }
        },
        {"$sort": {"time": 1}},
        {"$limit": limit},
    ]

    return await db["laps"].aggregate(pipeline).to_list(length=limit)


# ── Collection-level counts ────────────────────────────────────────

async def get_collection_counts(db: AsyncIOMotorDatabase) -> dict[str, int]:
    """Return document counts for all pipeline collections."""

    collections = [
        "leagues", "seasons", "stages", "teams", "drivers",
        "venues", "fixtures", "livescores", "driver_standings",
        "team_standings", "laps", "pitstops", "stints", "countries",
    ]

    counts: dict[str, int] = {}
    for name in collections:
        counts[name] = await db[name].estimated_document_count()

    return counts


# ── Combined statistics endpoint ────────────────────────────────────

async def get_overview_statistics(
    db: AsyncIOMotorDatabase,
    season_id: int | None = None,
) -> dict[str, Any]:
    """High-level overview combining counts + top performers."""

    counts = await get_collection_counts(db)
    top_drivers = await get_driver_statistics(db, season_id=season_id, limit=10)
    top_teams = await get_team_statistics(db, season_id=season_id, limit=10)

    return {
        "collection_counts": counts,
        "top_drivers": top_drivers,
        "top_teams": top_teams,
    }
