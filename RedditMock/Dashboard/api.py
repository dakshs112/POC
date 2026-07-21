import requests

BASE_URL = "http://localhost:8000"


def get_posts(limit=20):
    response = requests.get(
        f"{BASE_URL}/posts",
        params={"limit": limit}
    )
    return response.json()


def get_stats():
    response = requests.get(f"{BASE_URL}/stats")
    return response.json()


def get_authors():
    response = requests.get(f"{BASE_URL}/authors")
    return response.json()


def get_timeline():
    response = requests.get(f"{BASE_URL}/timeline")
    return response.json()


def sync_posts():
    response = requests.post(f"{BASE_URL}/sync")
    return response.json()