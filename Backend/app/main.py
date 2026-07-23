"""
FastAPI application factory and lifespan management.

This is the entry-point for the application:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

Lifespan events handle:
- MongoDB connection + index creation
- Sportmonks HTTP client initialisation
- APScheduler startup
- Graceful shutdown of all resources
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import close_db, ensure_indexes, init_db
from app.routes import router, set_sportmonks_client
from app.scheduler import init_scheduler, shutdown_scheduler, start_scheduler
from app.sportmonks_service import SportmonksClient
from app.utils import configure_logging, get_logger

logger = get_logger("f1_pipeline.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan — runs once at startup and once at shutdown.

    Startup:
        1. Configure structured logging
        2. Initialise MongoDB Motor client & create indexes
        3. Create and start the Sportmonks HTTP client
        4. Wire up the client to the routes layer
        5. Configure and start the APScheduler

    Shutdown:
        1. Stop the scheduler
        2. Close the Sportmonks HTTP client
        3. Close the MongoDB connection
    """
    settings = get_settings()

    # ── Startup ─────────────────────────────────────────────────────
    configure_logging(settings.LOG_LEVEL)
    logger.info("Starting F1 Data Ingestion Pipeline …")

    # MongoDB
    await init_db(settings)
    await ensure_indexes()

    # Sportmonks client
    sm_client = SportmonksClient(settings)
    await sm_client.start()
    set_sportmonks_client(sm_client)

    # Scheduler
    scheduler = init_scheduler(sm_client)
    start_scheduler()

    logger.info("Pipeline ready — all services initialised")

    yield  # ← application is running

    # ── Shutdown ────────────────────────────────────────────────────
    logger.info("Shutting down F1 Data Ingestion Pipeline …")
    shutdown_scheduler()
    await sm_client.close()
    await close_db()
    logger.info("Shutdown complete")


# ── App factory ─────────────────────────────────────────────────────

app = FastAPI(
    title="F1 Data Ingestion Pipeline",
    description=(
        "Production-grade data pipeline for Formula 1 using "
        "the Sportmonks Motorsport API v3. Supports automatic "
        "ingestion, scheduled syncs, and analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── Middleware ──────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ──────────────────────────────────────────────────────────

app.include_router(router, prefix="")
