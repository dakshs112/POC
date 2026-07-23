# 🏎️ F1 Data Ingestion Pipeline

A production-grade, async data ingestion pipeline for **Formula 1** data using the [Sportmonks Motorsport API v3](https://docs.sportmonks.com/formula-one).

Built with **FastAPI**, **httpx**, **Motor (MongoDB)**, and **APScheduler**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │  Routes   │  │  Scheduler   │  │   Analytics            │ │
│  │ (POST/GET)│  │ (APScheduler)│  │ (Aggregation Pipelines)│ │
│  └─────┬─────┘  └──────┬───────┘  └───────────┬────────────┘ │
│        │               │                      │              │
│        ▼               ▼                      │              │
│  ┌─────────────────────────────────┐          │              │
│  │     Sportmonks Service          │          │              │
│  │  ┌───────────────────────────┐  │          │              │
│  │  │   Endpoint Registry       │  │          │              │
│  │  │   (data-driven, no code)  │  │          │              │
│  │  └───────────────────────────┘  │          │              │
│  │  ┌───────────────────────────┐  │          │              │
│  │  │   HTTP Client (httpx)     │  │          │              │
│  │  │   • Pagination            │  │          │              │
│  │  │   • Rate limiting         │  │          │              │
│  │  │   • Retry w/ backoff      │  │          │              │
│  │  │   • Semaphore concurrency │  │          │              │
│  │  └───────────────────────────┘  │          │              │
│  └─────────────┬───────────────────┘          │              │
│                │                              │              │
│                ▼                              ▼              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  MongoDB Atlas (Motor)                   │ │
│  │   drivers │ teams │ fixtures │ standings │ laps │ ...    │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Folder Structure

```
Backend/
├── app/
│   ├── __init__.py              # Package marker
│   ├── config.py                # Pydantic-settings configuration
│   ├── database.py              # Motor client, upserts, indexes
│   ├── sportmonks_service.py    # Endpoint registry + ingestion engine
│   ├── routes.py                # FastAPI POST (sync) + GET (query) routes
│   ├── analytics.py             # MongoDB aggregation pipelines
│   ├── scheduler.py             # APScheduler background jobs
│   ├── utils.py                 # Logging, timing, normalizers
│   └── main.py                  # App factory & lifespan
├── requirements.txt
├── .env                         # Environment configuration
└── README.md                    # This file
```

---

## Prerequisites

- **Python 3.11+**
- **MongoDB Atlas** cluster (or local MongoDB)
- **Sportmonks API key** with Motorsport access

---

## Setup

### 1. Clone & Install

```bash
cd Backend
pip install -r requirements.txt
```

### 2. Configure `.env`

Edit the `.env` file in the project root:

```dotenv
SPORTMONKS_API_KEY=your_actual_api_key
SPORTMONKS_BASE_URL=https://api.sportmonks.com/v3/motorsport
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=f1_pipeline
REQUEST_TIMEOUT=30
MAX_CONCURRENT_REQUESTS=5
RETRY_MAX_ATTEMPTS=5
RETRY_BASE_DELAY=1.0
LOG_LEVEL=INFO
```

### 3. Run the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API docs are available at: **http://localhost:8000/docs**

---

## How to Sync Data

### Via API

| Action | Endpoint | Method |
|---|---|---|
| Full pipeline sync | `/sync/all` | `POST` |
| Sync drivers | `/sync/drivers` | `POST` |
| Sync teams | `/sync/teams` | `POST` |
| Sync races / fixtures | `/sync/races` | `POST` |
| Sync standings | `/sync/standings` | `POST` |
| Sync live data | `/sync/live` | `POST` |
| Sync seasons | `/sync/seasons` | `POST` |
| Sync venues | `/sync/venues` | `POST` |
| Sync laps | `/sync/laps` | `POST` |
| Sync pit-stops | `/sync/pitstops` | `POST` |

Example:

```bash
# Sync everything
curl -X POST http://localhost:8000/sync/all

# Sync just drivers
curl -X POST http://localhost:8000/sync/drivers
```

### Via Scheduler (Automatic)

The scheduler starts automatically and runs:

| Job | Interval | Data |
|---|---|---|
| Live data | Every 30 seconds | Livescores |
| Standings | Every 30 minutes | Driver & team standings |
| Fixtures | Every 6 hours | Fixtures & stages |
| Daily | Once per day | Drivers & teams |
| Historical | Once per week | Seasons, venues, countries, leagues |
| Deep data | Once per week | Laps, pit-stops, stints |

Check scheduler status: `GET /scheduler/status`

---

## Query Data

All GET endpoints support **pagination** (`page`, `per_page`) and **filtering**.

| Endpoint | Filters |
|---|---|
| `GET /drivers` | `season_id`, `team_id`, `search` |
| `GET /drivers/{id}` | — |
| `GET /teams` | `season_id`, `search` |
| `GET /teams/{id}` | — |
| `GET /races` | `season_id`, `venue_id`, `search` |
| `GET /races/{id}` | — |
| `GET /standings` | `season_id` |
| `GET /standings/drivers` | `season_id` |
| `GET /standings/teams` | `season_id` |
| `GET /results` | `season_id`, `fixture_id` |
| `GET /seasons` | `search` |
| `GET /venues` | `search` |
| `GET /laps` | `fixture_id`, `driver_id` |
| `GET /statistics` | `season_id` |
| `GET /statistics/drivers` | `season_id`, `limit` |
| `GET /statistics/teams` | `season_id`, `limit` |
| `GET /statistics/venues` | `limit` |
| `GET /statistics/pitstops` | `fixture_id`, `limit` |
| `GET /statistics/laps` | `fixture_id`, `limit` |

Example:

```bash
# Get all drivers, page 2
curl "http://localhost:8000/drivers?page=2&per_page=10"

# Search for a driver
curl "http://localhost:8000/drivers?search=verstappen"

# Get standings for a specific season
curl "http://localhost:8000/standings/drivers?season_id=21646"
```

---

## How to Add New Endpoints

The pipeline is **fully data-driven**. To collect data from a new Sportmonks endpoint, add a single entry to the `ENDPOINT_REGISTRY` in `app/sportmonks_service.py`:

```python
EndpointConfig(
    collection="new_collection_name",       # MongoDB collection
    path="/new-endpoint",                    # Sportmonks API path
    includes="related,data",                 # Optional includes
    category="daily",                        # Scheduler category
),
```

If the endpoint requires a parent ID (e.g., `season_id`):

```python
EndpointConfig(
    collection="new_scoped_data",
    path="/some-endpoint/season/{season_id}",
    requires_parent=True,
    parent_collection="seasons",
    parent_id_field="season_id",
    includes="participant",
    category="frequent",
),
```

Then add a normalizer function in `app/utils.py`:

```python
def normalize_new_entity(raw: dict) -> dict:
    return {
        "id": safe_get(raw, "id"),
        "name": safe_get(raw, "name"),
        # ... extract fields
    }

# Register it
NORMALIZERS["new_collection_name"] = normalize_new_entity
```

**That's it** — no new route code, no new sync logic needed.

---

## MongoDB Document Schema

Every document in every collection follows this schema:

```json
{
    "sportmonks_id": 12345,
    "fetched_at": "2026-07-22T10:00:00Z",
    "last_updated": "2026-07-22T12:00:00Z",
    "source_endpoint": "/drivers",
    "raw_response": { "... full API response ..." },
    "normalized": {
        "id": 12345,
        "name": "Max Verstappen",
        "country_id": 456,
        "..."
    }
}
```

- `raw_response` — preserves the complete API payload (nothing lost)
- `normalized` — extracted, flattened fields for easy querying
- Unique index on `sportmonks_id` per collection
- Upserts prevent duplicates

---

## Error Handling

| Error | Strategy |
|---|---|
| `429 Too Many Requests` | Wait `Retry-After` header, then retry |
| `401 Unauthorized` | Log and skip (no retry) |
| `5xx Server Error` | Exponential backoff (1s → 2s → 4s → 8s → 16s) |
| Timeout / Network | Same backoff, max 5 attempts |
| Any endpoint failure | Log error, continue pipeline |

The pipeline **never crashes**. Failed endpoints are logged and skipped.

---

## Tech Stack

| Component | Technology |
|---|---|
| Web framework | FastAPI |
| HTTP client | httpx (async) |
| Database | MongoDB Atlas via Motor |
| Scheduler | APScheduler |
| Config | pydantic-settings + python-dotenv |
| Logging | structlog (JSON) |
| Language | Python 3.11+ |
