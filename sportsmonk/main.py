from enum import Enum
import os
from typing import List, Optional
# 1. FIXED: Added 'Path' to the imports
from fastapi import FastAPI, HTTPException, Path, Query
import httpx


# ---------------------------------------------------------------------------
# 1. ENUMS FOR SWAGGER DROPDOWNS
# Defining an Enum automatically renders as a dropdown menu in /docs
# ---------------------------------------------------------------------------
class StandingsCategory(str, Enum):
    """Select between Driver or Constructor Championship Standings"""

    # FIXED: Updated to standard Motorsport v3 standings endpoint
    ALL_STANDINGS = "standings"
    BY_SEASON = "standings/seasons"


class FixtureIncludeOption(str, Enum):
    """Enrich race/fixture data with detailed F1 telemetry and results"""

    RESULTS = "results"  # Final race positions, time intervals, gaps
    VENUE = "venue"  # Track details (e.g., Albert Park, Monza)
    STATE = "state"  # Current race status (e.g., Finished, Flagged)
    PITSTOPS = "pitstops"  # Detailed pitstop times and tire changes
    STINTS = "stints"  # Tire compound history per driver
    LINEUPS = "lineups"  # Starting grid positions
    PARTICIPANTS = "participants"  # Driver & Team names


class LiveIncludeOption(str, Enum):
    """Includes for real-time live race tracking"""

    STATE = "state"
    PARTICIPANTS = "participants"
    VENUE = "venue"
    RESULTS = "results"


# ---------------------------------------------------------------------------
# 2. APP INITIALIZATION & CONFIG
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Sportmonks Formula 1 (Motorsport v3) API Proxy",
    description="A FastAPI gateway for Formula 1 data with built-in interactive Swagger UI dropdowns.",
    version="1.0.0",
)

# Paste your API token here OR set it as an OS Environment Variable
SPORTMONKS_API_TOKEN = os.getenv(
    "SPORTMONKS_API_TOKEN", "BKbNsUp8B5m6ZvbwItnvYyUQgr2Xg7YCBeJPUJ6nzsR4kZMtFqaFOfgj8N9y"
)
BASE_URL = "https://api.sportmonks.com/v3/motorsport"


# ---------------------------------------------------------------------------
# 3. HELPER FUNCTION TO FETCH DATA
# ---------------------------------------------------------------------------
async def fetch_from_sportmonks(endpoint: str, params: dict):
    """Handles async requests to the Sportmonks Motorsport API with error handling."""
    params["api_token"] = SPORTMONKS_API_TOKEN

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/{endpoint}", params=params, timeout=10.0
            )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, detail=f"Failed to connect to Sportmonks: {str(e)}"
            )

        # Handle API-level errors
        if response.status_code in [401, 403]:
            raise HTTPException(
                status_code=response.status_code,
                detail="Access Denied: Invalid Token or your plan does not cover Formula 1 / Motorsport endpoints.",
            )
        elif response.status_code == 429:
            raise HTTPException(
                status_code=429, detail="Rate Limit Exceeded on Sportmonks API."
            )
        elif response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code, detail=response.text
            )

        return response.json()


# ---------------------------------------------------------------------------
# 4. API ENDPOINTS
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Welcome! Go to http://127.0.0.1:8000/docs to test the interactive F1 Swagger UI dropdowns."
    }


@app.get("/championship-standings")
async def get_standings(
    category: StandingsCategory = Query(
        StandingsCategory.ALL_STANDINGS,
        description="Select the Standings endpoint from the dropdown",
    ),
    include_participant: bool = Query(
        True,
        description="Include full Driver or Team profile details in the standings table",
    ),
):
    """**Fetch F1 Championship Standings** using a dropdown menu."""
    params = {}
    if include_participant:
        params["include"] = "participant"

    data = await fetch_from_sportmonks(category.value, params)
    return data


@app.get("/race-details/{fixture_id}")
async def get_race_details(
    # 2. FIXED: Swapped 'Query' for 'Path' here to match the URL {fixture_id} variable
    fixture_id: int = Path(
        ...,
        description="Enter the Sportmonks Fixture ID for a specific Grand Prix session",
    ),
    includes: Optional[List[FixtureIncludeOption]] = Query(
        default=[FixtureIncludeOption.RESULTS, FixtureIncludeOption.VENUE],
        description="Select additional race telemetry to include (multi-select supported)",
    ),
):
    """**Fetch Grand Prix Race Results & Telemetry** (Pitstops, Tire Stints, Starting Grid, etc.) by Fixture ID."""
    params = {}
    if includes:
        # Join multiple includes with a semicolon as required by Sportmonks v3
        params["include"] = ";".join([inc.value for inc in includes])

    data = await fetch_from_sportmonks(f"fixtures/{fixture_id}", params)
    return data


@app.get("/live-races")
async def get_live_races(
    includes: Optional[List[LiveIncludeOption]] = Query(
        default=[LiveIncludeOption.STATE, LiveIncludeOption.PARTICIPANTS],
        description="Select data to include for currently active race sessions",
    ),
):
    """**Fetch Live F1 Race Sessions** currently happening right now."""
    params = {}
    if includes:
        params["include"] = ";".join([inc.value for inc in includes])

    data = await fetch_from_sportmonks("livescores", params)
    return data