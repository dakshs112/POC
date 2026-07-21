from fastapi import APIRouter,Query

from app.analytics import AnalyticsService
from app.reddit_service import RedditRSSService

router = APIRouter()

analytics = AnalyticsService()

reddit = RedditRSSService()


@router.get("/posts")
async def get_posts(
    limit: int = Query(default=20, ge=1, le=100)
):
    return await analytics.get_posts(limit)


@router.get("/stats")
async def get_stats():

    return await analytics.get_stats()


@router.get("/authors")
async def get_authors():

    return await analytics.get_top_authors()


@router.get("/timeline")
async def get_timeline():

    return await analytics.get_posts_timeline()


@router.post("/sync")
async def sync():

    return await reddit.save_posts()