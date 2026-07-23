import os
import requests

BASE_URL = os.getenv("REDDIT_DASHBOARD_API_URL", "http://localhost:8000")
TIMEOUT = 10


def _get(path, params=None, default=None):
    try:
        response = requests.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return default if default is not None else []


def get_posts(limit=20):
    return _get("/posts", params={"limit": limit}, default=[])


def get_stats():
    return _get(
        "/stats",
        default={"total_posts": 0, "unique_authors": 0, "last_updated": "—"},
    )


def get_authors():
    return _get("/authors", default=[])


def get_timeline():
    return _get("/timeline", default=[])


def sync_posts():
    try:
        response = requests.post(f"{BASE_URL}/sync", timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"error": str(exc)}