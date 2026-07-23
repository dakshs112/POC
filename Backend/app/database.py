"""
MongoDB database layer (Motor async client).

Provides:
- Connection lifecycle helpers (init / close)
- Collection accessor
- Document upsert with the standard schema
- Bulk upsert helper
- Index creation at startup
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo import UpdateOne

from app.config import Settings

logger = logging.getLogger("f1_pipeline.database")

# ── Module-level state ──────────────────────────────────────────────
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


# ── Lifecycle ───────────────────────────────────────────────────────

async def init_db(settings: Settings) -> None:
    """Initialise the Motor client and database reference."""
    global _client, _db
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _db = _client[settings.MONGODB_DATABASE]
    logger.info("MongoDB connected → database '%s'", settings.MONGODB_DATABASE)


async def close_db() -> None:
    """Gracefully close the Motor client."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Return the active database handle (raises if not initialised)."""
    if _db is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    return _db


def get_collection(name: str) -> AsyncIOMotorCollection:
    """Return a collection by name from the active database."""
    return get_database()[name]


# ── Index creation ──────────────────────────────────────────────────

async def ensure_indexes() -> None:
    """Create a unique index on `sportmonks_id` for every known collection."""
    db = get_database()

    collections = [
        "leagues", "seasons", "stages", "teams", "drivers",
        "venues", "fixtures", "livescores", "driver_standings",
        "team_standings", "laps", "pitstops", "stints", "countries",
    ]

    for coll_name in collections:
        coll = db[coll_name]
        await coll.create_index("sportmonks_id", unique=True, background=True)

    logger.info("Ensured indexes on %d collections", len(collections))


# ── Document helpers ────────────────────────────────────────────────

def _build_document(
    sportmonks_id: int | str,
    raw_response: dict[str, Any],
    source_endpoint: str,
    normalized: dict[str, Any],
) -> dict[str, Any]:
    """Build the standard document schema stored in every collection."""
    now = datetime.now(timezone.utc)
    return {
        "sportmonks_id": sportmonks_id,
        "fetched_at": now,
        "last_updated": now,
        "source_endpoint": source_endpoint,
        "raw_response": raw_response,
        "normalized": normalized,
    }


async def upsert_document(
    collection: AsyncIOMotorCollection,
    sportmonks_id: int | str,
    raw_response: dict[str, Any],
    source_endpoint: str,
    normalized: dict[str, Any],
) -> str:
    """
    Upsert a single document by sportmonks_id.

    Returns:
        "inserted" | "updated" | "skipped"
    """
    now = datetime.now(timezone.utc)
    result = await collection.update_one(
        {"sportmonks_id": sportmonks_id},
        {
            "$set": {
                "last_updated": now,
                "source_endpoint": source_endpoint,
                "raw_response": raw_response,
                "normalized": normalized,
            },
            "$setOnInsert": {
                "sportmonks_id": sportmonks_id,
                "fetched_at": now,
            },
        },
        upsert=True,
    )

    if result.upserted_id is not None:
        return "inserted"
    if result.modified_count > 0:
        return "updated"
    return "skipped"


async def upsert_many(
    collection: AsyncIOMotorCollection,
    documents: list[dict[str, Any]],
    source_endpoint: str,
) -> dict[str, int]:
    """
    Bulk-upsert a list of documents.

    Each item in *documents* must contain at minimum:
        sportmonks_id, raw_response, normalized

    Returns:
        {"inserted": N, "updated": N, "skipped": N}
    """
    if not documents:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    now = datetime.now(timezone.utc)
    operations: list[UpdateOne] = []

    for doc in documents:
        sid = doc["sportmonks_id"]
        operations.append(
            UpdateOne(
                {"sportmonks_id": sid},
                {
                    "$set": {
                        "last_updated": now,
                        "source_endpoint": source_endpoint,
                        "raw_response": doc["raw_response"],
                        "normalized": doc["normalized"],
                    },
                    "$setOnInsert": {
                        "sportmonks_id": sid,
                        "fetched_at": now,
                    },
                },
                upsert=True,
            )
        )

    result = await collection.bulk_write(operations, ordered=False)

    return {
        "inserted": result.upserted_count,
        "updated": result.modified_count,
        "skipped": len(documents) - result.upserted_count - result.modified_count,
    }
