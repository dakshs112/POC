"""
Sportmonks Motorsport API v3 — Data Ingestion Service.

This is the core of the pipeline.  It provides:
- A declarative ENDPOINT_REGISTRY (add a row → new data collected automatically)
- Async HTTP fetching with pagination, rate-limit handling, and retries
- Recursive parent-resolution (seasons → stages → fixtures → laps …)
- Semaphore-limited concurrency via asyncio.gather
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.database import get_collection, upsert_many
from app.utils import get_logger, normalize_record, timed

logger = get_logger("f1_pipeline.service")


# ══════════════════════════════════════════════════════════════════════
# Endpoint Registry — fully data-driven, no per-endpoint code paths
# ══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class EndpointConfig:
    """Declarative configuration for a single Sportmonks endpoint."""

    collection: str
    """MongoDB collection name for storing fetched records."""

    path: str
    """
    URL path relative to the base URL.
    May contain ``{season_id}``, ``{fixture_id}`` etc. which are resolved
    automatically from the parent collection.
    """

    requires_parent: bool = False
    """If True, the path contains a placeholder that must be filled by
    iterating over documents in *parent_collection*."""

    parent_collection: str = ""
    """The MongoDB collection to read parent IDs from."""

    parent_id_field: str = ""
    """The placeholder name inside *path* (e.g. ``season_id``)."""

    includes: str = ""
    """Comma-separated ``include`` parameter for the Sportmonks request."""

    category: str = "general"
    """Logical grouping — used by ``sync_category()`` and the scheduler."""

    store_collection: str = ""
    """
    Override the collection name used for *storing* results.
    When empty the *collection* field is used.  This is useful when
    e.g. ``fixtures_by_season`` should store into ``fixtures``.
    """

    @property
    def target_collection(self) -> str:
        return self.store_collection or self.collection


# ── The registry ────────────────────────────────────────────────────

ENDPOINT_REGISTRY: list[EndpointConfig] = [
    # ── Top-level entities ──
    EndpointConfig(
        collection="leagues",
        path="/leagues",
        category="historical",
    ),
    EndpointConfig(
        collection="countries",
        path="/countries",
        category="historical",
    ),
    EndpointConfig(
        collection="seasons",
        path="/seasons",
        category="historical",
    ),
    EndpointConfig(
        collection="teams",
        path="/teams",
        category="daily",
    ),
    EndpointConfig(
        collection="drivers",
        path="/drivers",
        category="daily",
    ),
    EndpointConfig(
        collection="venues",
        path="/venues",
        category="historical",
    ),

    # ── Season-scoped entities ──
    EndpointConfig(
        collection="stages",
        path="/stages/season/{season_id}",
        requires_parent=True,
        parent_collection="seasons",
        parent_id_field="season_id",
        category="frequent",
    ),
    EndpointConfig(
        collection="teams_by_season",
        path="/teams/season/{season_id}",
        requires_parent=True,
        parent_collection="seasons",
        parent_id_field="season_id",
        store_collection="teams",
        category="daily",
    ),
    EndpointConfig(
        collection="drivers_by_season",
        path="/drivers/season/{season_id}",
        requires_parent=True,
        parent_collection="seasons",
        parent_id_field="season_id",
        store_collection="drivers",
        category="daily",
    ),
    EndpointConfig(
        collection="venues_by_season",
        path="/venues/season/{season_id}",
        requires_parent=True,
        parent_collection="seasons",
        parent_id_field="season_id",
        store_collection="venues",
        category="historical",
    ),
    EndpointConfig(
        collection="fixtures_by_season",
        path="/fixtures/season/{season_id}",
        requires_parent=True,
        parent_collection="seasons",
        parent_id_field="season_id",
        store_collection="fixtures",
        category="frequent",
    ),

    # ── Standings ──
    EndpointConfig(
        collection="driver_standings",
        path="/standings/drivers/season/{season_id}",
        requires_parent=True,
        parent_collection="seasons",
        parent_id_field="season_id",
        category="standings",
    ),
    EndpointConfig(
        collection="team_standings",
        path="/standings/teams/season/{season_id}",
        requires_parent=True,
        parent_collection="seasons",
        parent_id_field="season_id",
        category="standings",
    ),

    # ── Deep data ──
    EndpointConfig(
        collection="laps",
        path="/fixtures/{fixture_id}/laps",
        requires_parent=True,
        parent_collection="fixtures",
        parent_id_field="fixture_id",
        category="deep",
    ),
    EndpointConfig(
        collection="pitstops",
        path="/fixtures/{fixture_id}/pitstops",
        requires_parent=True,
        parent_collection="fixtures",
        parent_id_field="fixture_id",
        category="deep",
    ),
    EndpointConfig(
        collection="stints",
        path="/fixtures/{fixture_id}/stints",
        requires_parent=True,
        parent_collection="fixtures",
        parent_id_field="fixture_id",
        category="deep",
    ),

    # ── Live ──
    EndpointConfig(
        collection="livescores",
        path="/livescores",
        category="live",
    ),
    EndpointConfig(
        collection="livescores_inplay",
        path="/livescores/inplay",
        store_collection="livescores",
        category="live",
    ),
]
# Build lookup dicts for quick access
_REGISTRY_BY_COLLECTION: dict[str, EndpointConfig] = {
    ep.collection: ep for ep in ENDPOINT_REGISTRY
}
_REGISTRY_BY_CATEGORY: dict[str, list[EndpointConfig]] = {}
for _ep in ENDPOINT_REGISTRY:
    _REGISTRY_BY_CATEGORY.setdefault(_ep.category, []).append(_ep)


# ══════════════════════════════════════════════════════════════════════
# Sync result tracking
# ══════════════════════════════════════════════════════════════════════

@dataclass
class SyncResult:
    """Aggregated counters for a single endpoint sync."""
    endpoint: str = ""
    status: str = "pending"
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: float = 0.0

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.skipped

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "status": self.status,
            "records_inserted": self.inserted,
            "records_updated": self.updated,
            "records_skipped": self.skipped,
            "errors": self.errors,
            "duration_ms": round(self.duration_ms, 2),
        }


# ══════════════════════════════════════════════════════════════════════
# Sportmonks HTTP Client
# ══════════════════════════════════════════════════════════════════════

class SportmonksClient:
    """
    Async HTTP client wrapper for the Sportmonks Motorsport API.

    Handles authentication, pagination, rate-limiting (429), retries
    with exponential backoff, and concurrency control.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(self._settings.MAX_CONCURRENT_REQUESTS)

    # ── lifecycle ───────────────────────────────────────────────────

    async def start(self) -> None:
        """Create the underlying httpx client."""
        self._client = httpx.AsyncClient(
            base_url=self._settings.SPORTMONKS_BASE_URL,
            timeout=httpx.Timeout(self._settings.REQUEST_TIMEOUT),
            headers={
                "Accept": "application/json",
                "Authorization": self._settings.SPORTMONKS_API_KEY,
            },
        )
        logger.info("SportmonksClient started", base_url=self._settings.SPORTMONKS_BASE_URL)

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("SportmonksClient closed")

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("SportmonksClient not started — call start() first")
        return self._client

    # ── single request with retries ─────────────────────────────────

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a single GET request with exponential-backoff retry.

        Handles:
          429 — wait ``Retry-After`` header (or default back-off)
          401 — log and raise immediately (no retry)
          5xx — retry with back-off
          Timeout / network — retry with back-off
        """
        max_attempts = self._settings.RETRY_MAX_ATTEMPTS
        base_delay = self._settings.RETRY_BASE_DELAY
        merged_params = dict(params or {})
        merged_params["api_token"] = self._settings.SPORTMONKS_API_KEY

        for attempt in range(1, max_attempts + 1):
            try:
                async with self._semaphore:
                    resp = await self.client.get(path, params=merged_params)

                if resp.status_code == 200:
                    return resp.json()

                if resp.status_code == 401:
                    logger.error("auth_failed", path=path, status=401)
                    raise PermissionError(f"401 Unauthorized for {path}")

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", base_delay * attempt))
                    logger.warning(
                        "rate_limited",
                        path=path,
                        retry_after=retry_after,
                        attempt=attempt,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code >= 500:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "server_error",
                        path=path,
                        status=resp.status_code,
                        retry_in=delay,
                        attempt=attempt,
                    )
                    await asyncio.sleep(delay)
                    continue

                # Other 4xx — log and give up
                logger.error(
                    "request_failed",
                    path=path,
                    status=resp.status_code,
                    body=resp.text[:500],
                )
                return {"data": []}

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "network_error",
                    path=path,
                    error=str(exc),
                    retry_in=delay,
                    attempt=attempt,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(delay)
                else:
                    logger.error("request_exhausted", path=path, attempts=max_attempts)
                    return {"data": []}

        return {"data": []}

    # ── paginated fetch ─────────────────────────────────────────────

    async def fetch_all_pages(
        self,
        path: str,
        includes: str = "",
    ) -> list[dict[str, Any]]:
        """
        Fetch every page for an endpoint using cursor-based pagination.

        Returns the accumulated ``data`` arrays across all pages.
        """
        all_records: list[dict[str, Any]] = []
        page = 1

        params: dict[str, Any] = {}
        if includes:
            params["include"] = includes

        while True:
            params["page"] = page
            response = await self._request(path, params)
            print("\n" + "=" * 80)
            print("PATH:", path)
            print("RESPONSE:")
            print(response)
            print("=" * 80 + "\n")

            data = response.get("data")
            if data is None:
                # Some endpoints return a single object instead of a list
                if isinstance(response.get("data"), dict):
                    all_records.append(response["data"])
                break

            if isinstance(data, list):
                all_records.extend(data)
            elif isinstance(data, dict):
                all_records.append(data)

            # Check for more pages
            pagination = response.get("pagination", {})
            has_more = pagination.get("has_more", False)
            if not has_more:
                break

            next_page = pagination.get("current_page", page) + 1
            page = next_page

        return all_records

    # ── parent-ID resolver ──────────────────────────────────────────

    async def _get_parent_ids(self, parent_collection: str) -> list[int | str]:
        """Read all sportmonks_id values from a parent collection in MongoDB."""
        coll = get_collection(parent_collection)
        cursor = coll.find({}, {"sportmonks_id": 1, "_id": 0})
        ids = [doc["sportmonks_id"] async for doc in cursor]
        logger.info(
            "parent_ids_loaded",
            parent_collection=parent_collection,
            count=len(ids),
        )
        return ids

    # ── single-endpoint sync ────────────────────────────────────────

    @timed
    async def sync_endpoint(self, ep: EndpointConfig) -> SyncResult:
        """
        Run the full ingest cycle for one EndpointConfig:

        1. If no parent required → fetch all pages, upsert.
        2. If parent required → load parent IDs, fan-out requests
           with semaphore concurrency, aggregate results.
        """
        result = SyncResult(endpoint=ep.collection)
        start = time.perf_counter()

        try:
            if not ep.requires_parent:
                records = await self.fetch_all_pages(ep.path, ep.includes)
                counts = await self._store_records(ep, records)
                result.inserted = counts["inserted"]
                result.updated = counts["updated"]
                result.skipped = counts["skipped"]
            else:
                parent_ids = await self._get_parent_ids(ep.parent_collection)
                if not parent_ids:
                    logger.warning(
                        "no_parent_ids",
                        endpoint=ep.collection,
                        parent=ep.parent_collection,
                    )
                    result.status = "skipped_no_parents"
                    return result

                # Fan-out with concurrency limit
                tasks = [
                    self._sync_for_parent(ep, pid)
                    for pid in parent_ids
                ]
                sub_results = await asyncio.gather(*tasks, return_exceptions=True)

                for sr in sub_results:
                    if isinstance(sr, Exception):
                        result.errors += 1
                        logger.error(
                            "parent_sync_error",
                            endpoint=ep.collection,
                            error=str(sr),
                        )
                    elif isinstance(sr, dict):
                        result.inserted += sr.get("inserted", 0)
                        result.updated += sr.get("updated", 0)
                        result.skipped += sr.get("skipped", 0)

            result.status = "completed"

        except PermissionError:
            result.status = "auth_failed"
            result.errors += 1
        except Exception as exc:
            result.status = "failed"
            result.errors += 1
            logger.error(
                "sync_endpoint_failed",
                endpoint=ep.collection,
                error=str(exc),
                exc_info=True,
            )
        finally:
            result.duration_ms = (time.perf_counter() - start) * 1000
            logger.info("sync_endpoint_result", **result.as_dict())

        return result

    async def _sync_for_parent(
        self,
        ep: EndpointConfig,
        parent_id: int | str,
    ) -> dict[str, int]:
        """Fetch and store records for a single parent ID."""
        path = ep.path.replace(f"{{{ep.parent_id_field}}}", str(parent_id))
        records = await self.fetch_all_pages(path, ep.includes)
        return await self._store_records(ep, records)

    async def _store_records(
        self,
        ep: EndpointConfig,
        records: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Normalize and bulk-upsert a batch of raw records."""
        if not records:
            return {"inserted": 0, "updated": 0, "skipped": 0}

        documents = []
        for raw in records:
            sid = raw.get("id")
            if sid is None:
                continue
            documents.append(
                {
                    "sportmonks_id": sid,
                    "raw_response": raw,
                    "normalized": normalize_record(ep.target_collection, raw),
                }
            )

        coll = get_collection(ep.target_collection)
        return await upsert_many(coll, documents, ep.path)

    # ── orchestration ───────────────────────────────────────────────

    @timed
    async def sync_all(self) -> list[dict[str, Any]]:
        """Sync every endpoint in the registry (respects dependency order)."""
        # Phase 1: top-level (no parent)
        top_level = [ep for ep in ENDPOINT_REGISTRY if not ep.requires_parent]
        results = await asyncio.gather(
            *(self.sync_endpoint(ep) for ep in top_level),
            return_exceptions=True,
        )

        # Phase 2: parent-dependent (now that parents are stored)
        dependent = [ep for ep in ENDPOINT_REGISTRY if ep.requires_parent]
        dep_results = await asyncio.gather(
            *(self.sync_endpoint(ep) for ep in dependent),
            return_exceptions=True,
        )

        all_results: list[dict[str, Any]] = []
        for r in list(results) + list(dep_results):
            if isinstance(r, SyncResult):
                all_results.append(r.as_dict())
            elif isinstance(r, Exception):
                all_results.append({"endpoint": "unknown", "status": "error", "error": str(r)})

        return all_results

    @timed
    async def sync_category(self, category: str) -> list[dict[str, Any]]:
        """Sync all endpoints belonging to *category*."""
        endpoints = _REGISTRY_BY_CATEGORY.get(category, [])
        if not endpoints:
            logger.warning("unknown_category", category=category)
            return []

        # Separate into top-level and dependent for correct ordering
        top_level = [ep for ep in endpoints if not ep.requires_parent]
        dependent = [ep for ep in endpoints if ep.requires_parent]

        all_results: list[dict[str, Any]] = []

        if top_level:
            results = await asyncio.gather(
                *(self.sync_endpoint(ep) for ep in top_level),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, SyncResult):
                    all_results.append(r.as_dict())
                elif isinstance(r, Exception):
                    all_results.append({"status": "error", "error": str(r)})

        if dependent:
            results = await asyncio.gather(
                *(self.sync_endpoint(ep) for ep in dependent),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, SyncResult):
                    all_results.append(r.as_dict())
                elif isinstance(r, Exception):
                    all_results.append({"status": "error", "error": str(r)})

        return all_results

    @timed
    async def sync_collection(self, collection_name: str) -> dict[str, Any]:
        """Sync a single collection by name."""
        ep = _REGISTRY_BY_COLLECTION.get(collection_name)
        if ep is None:
            logger.warning("unknown_collection", collection=collection_name)
            return {"status": "error", "message": f"Unknown collection: {collection_name}"}
        result = await self.sync_endpoint(ep)
        return result.as_dict()

    @timed
    async def sync_live(self) -> list[dict[str, Any]]:
        """Sync only live endpoints (livescores)."""
        return await self.sync_category("live")
