"""
Shared utilities — structured logging, timing, and field normalizers.

Provides:
- Structured JSON logging configuration
- @timed decorator for measuring execution time
- Per-entity normalizer functions that flatten raw Sportmonks responses
- safe_get() for deep dict access
"""

from __future__ import annotations

import functools
import logging
import logging.config
import time
from typing import Any, Callable

import structlog


# ── Structured logging setup ────────────────────────────────────────

def configure_logging(log_level: str = "INFO") -> None:
    """Set up structlog with JSON rendering on top of stdlib logging."""

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.add_log_level,
                        structlog.stdlib.add_logger_name,
                        structlog.processors.TimeStamper(fmt="iso"),
                        structlog.processors.StackInfoRenderer(),
                        structlog.processors.format_exc_info,
                        structlog.processors.JSONRenderer(),
                    ],
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                },
            },
            "root": {
                "handlers": ["console"],
                "level": log_level.upper(),
            },
        }
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)


# ── Timing decorator ───────────────────────────────────────────────

def timed(func: Callable) -> Callable:
    """Decorator that logs the wall-clock execution time of a function."""

    logger = get_logger("f1_pipeline.timing")

    @functools.wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "function_completed",
                function=func.__qualname__,
                duration_ms=round(elapsed_ms, 2),
            )
            return result
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "function_failed",
                function=func.__qualname__,
                duration_ms=round(elapsed_ms, 2),
            )
            raise

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "function_completed",
                function=func.__qualname__,
                duration_ms=round(elapsed_ms, 2),
            )
            return result
        except Exception:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "function_failed",
                function=func.__qualname__,
                duration_ms=round(elapsed_ms, 2),
            )
            raise

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# ── Safe dict access ────────────────────────────────────────────────

def safe_get(data: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    """
    Safely traverse nested dicts.

    >>> safe_get({"a": {"b": 1}}, "a", "b")
    1
    >>> safe_get({"a": {"b": 1}}, "a", "c", default="N/A")
    'N/A'
    """
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


# ── Field normalizers (per entity type) ─────────────────────────────

def normalize_league(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw league response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "short_code": safe_get(raw, "short_code"),
        "image_path": safe_get(raw, "image_path"),
        "type": safe_get(raw, "type"),
        "active": safe_get(raw, "active"),
        "country_id": safe_get(raw, "country_id"),
    }


def normalize_season(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw season response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "league_id": safe_get(raw, "league_id"),
        "is_current": safe_get(raw, "is_current_season"),
        "starting_at": safe_get(raw, "starting_at"),
        "ending_at": safe_get(raw, "ending_at"),
        "standings_recalculated_at": safe_get(raw, "standings_recalculated_at"),
    }


def normalize_stage(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw stage (race weekend) response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "type": safe_get(raw, "type"),
        "season_id": safe_get(raw, "season_id"),
        "league_id": safe_get(raw, "league_id"),
        "venue_id": safe_get(raw, "venue_id"),
        "sort_order": safe_get(raw, "sort_order"),
        "finished": safe_get(raw, "finished"),
        "is_current": safe_get(raw, "is_current"),
        "starting_at": safe_get(raw, "starting_at"),
        "ending_at": safe_get(raw, "ending_at"),
    }


def normalize_team(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw team/constructor response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "short_code": safe_get(raw, "short_code"),
        "image_path": safe_get(raw, "image_path"),
        "country_id": safe_get(raw, "country_id"),
        "founded": safe_get(raw, "founded"),
        "type": safe_get(raw, "type"),
    }


def normalize_driver(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw driver/participant response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "display_name": safe_get(raw, "display_name"),
        "first_name": safe_get(raw, "firstname"),
        "last_name": safe_get(raw, "lastname"),
        "image_path": safe_get(raw, "image_path"),
        "country_id": safe_get(raw, "country_id"),
        "nationality": safe_get(raw, "nationality"),
        "date_of_birth": safe_get(raw, "date_of_birth"),
        "gender": safe_get(raw, "gender"),
    }


def normalize_venue(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw venue/circuit response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "city": safe_get(raw, "city_name"),
        "country_id": safe_get(raw, "country_id"),
        "image_path": safe_get(raw, "image_path"),
        "capacity": safe_get(raw, "capacity"),
        "surface": safe_get(raw, "surface"),
        "address": safe_get(raw, "address"),
        "latitude": safe_get(raw, "latitude"),
        "longitude": safe_get(raw, "longitude"),
    }


def normalize_fixture(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw fixture/session response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "type": safe_get(raw, "type"),
        "season_id": safe_get(raw, "season_id"),
        "stage_id": safe_get(raw, "stage_id"),
        "league_id": safe_get(raw, "league_id"),
        "venue_id": safe_get(raw, "venue_id"),
        "state_id": safe_get(raw, "state_id"),
        "starting_at": safe_get(raw, "starting_at"),
        "ending_at": safe_get(raw, "ending_at"),
        "result_info": safe_get(raw, "result_info"),
        "has_odds": safe_get(raw, "has_odds"),
    }


def normalize_livescore(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw livescore response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "type": safe_get(raw, "type"),
        "season_id": safe_get(raw, "season_id"),
        "stage_id": safe_get(raw, "stage_id"),
        "league_id": safe_get(raw, "league_id"),
        "venue_id": safe_get(raw, "venue_id"),
        "state_id": safe_get(raw, "state_id"),
        "starting_at": safe_get(raw, "starting_at"),
        "result_info": safe_get(raw, "result_info"),
    }


def normalize_standing(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw standings entry."""
    return {
        "id": safe_get(raw, "id"),
        "participant_id": safe_get(raw, "participant_id"),
        "season_id": safe_get(raw, "season_id"),
        "league_id": safe_get(raw, "league_id"),
        "stage_id": safe_get(raw, "stage_id"),
        "position": safe_get(raw, "position"),
        "points": safe_get(raw, "points"),
        "form": safe_get(raw, "form"),
    }


def normalize_lap(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw lap data entry."""
    return {
        "id": safe_get(raw, "id"),
        "fixture_id": safe_get(raw, "fixture_id"),
        "participant_id": safe_get(raw, "participant_id"),
        "driver_id": safe_get(raw, "driver_id"),
        "lap_number": safe_get(raw, "number"),
        "position": safe_get(raw, "position"),
        "time": safe_get(raw, "time"),
        "gap": safe_get(raw, "gap"),
        "interval": safe_get(raw, "interval"),
        "is_fastest": safe_get(raw, "is_fastest"),
    }


def normalize_pitstop(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw pit stop entry."""
    return {
        "id": safe_get(raw, "id"),
        "fixture_id": safe_get(raw, "fixture_id"),
        "participant_id": safe_get(raw, "participant_id"),
        "driver_id": safe_get(raw, "driver_id"),
        "lap_number": safe_get(raw, "lap"),
        "duration": safe_get(raw, "duration"),
        "stop_number": safe_get(raw, "stop"),
    }


def normalize_stint(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw stint entry."""
    return {
        "id": safe_get(raw, "id"),
        "fixture_id": safe_get(raw, "fixture_id"),
        "participant_id": safe_get(raw, "participant_id"),
        "driver_id": safe_get(raw, "driver_id"),
        "compound": safe_get(raw, "compound"),
        "start_lap": safe_get(raw, "start_lap"),
        "end_lap": safe_get(raw, "end_lap"),
        "laps": safe_get(raw, "laps"),
    }


def normalize_country(raw: dict[str, Any]) -> dict[str, Any]:
    """Extract key fields from a raw country response."""
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        "official_name": safe_get(raw, "official_name"),
        "code": safe_get(raw, "code_alpha2"),
        "code_alpha3": safe_get(raw, "code_alpha3"),
        "continent": safe_get(raw, "continent"),
        "image_path": safe_get(raw, "image_path"),
    }


# ── Normalizer registry (maps collection name → normalizer fn) ─────

NORMALIZERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "leagues": normalize_league,
    "seasons": normalize_season,
    "stages": normalize_stage,
    "teams": normalize_team,
    "teams_by_season": normalize_team,
    "drivers": normalize_driver,
    "drivers_by_season": normalize_driver,
    "venues": normalize_venue,
    "venues_by_season": normalize_venue,
    "fixtures": normalize_fixture,
    "fixtures_by_season": normalize_fixture,
    "livescores": normalize_livescore,
    "livescores_inplay": normalize_livescore,
    "driver_standings": normalize_standing,
    "team_standings": normalize_standing,
    "laps": normalize_lap,
    "pitstops": normalize_pitstop,
    "stints": normalize_stint,
    "countries": normalize_country,
}


def normalize_record(collection: str, raw: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a raw Sportmonks record using the appropriate entity normalizer.

    Falls back to returning the raw record if no normalizer is registered.
    """
    normalizer = NORMALIZERS.get(collection)
    if normalizer is None:
        return dict(raw)
    return normalizer(raw)
