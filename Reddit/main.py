from datetime import datetime
import os
import dotenv
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
import feedparser
import httpx
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI(
    title="F1 Social Data RSS Engine with MongoDB",
    description="A credential-free FastAPI service that fetches live r/formula1 feed data via native RSS and stores it in MongoDB.",
    version="1.1.0",
)

MONGO_DETAILS = os.getenv("MONGO_DETAILS", "MONGO_URI")
client = AsyncIOMotorClient(MONGO_DETAILS)

# Define Database and Collection
db = client.f1_platform
posts_collection = db.reddit_posts

async def fetch_and_store_rss(feed_type: str = "hot", limit: int = 5):
    """
    Fetches public subreddit data using Reddit's native RSS engine,
    formats it, and updates/stores it inside a local MongoDB instance.
    """
    url = f"https://www.reddit.com/r/formula1/{feed_type}.rss"
    headers = {
        "User-Agent": "F1PlatformMockTrial/2026.1 (FastAPI Backend Server; Read-Only Proxy)"
    }
    
    async with httpx.AsyncClient() as client_ctx:
        try:
            response = await client_ctx.get(url, headers=headers, timeout=10.0)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code, 
                    detail=f"Reddit RSS endpoint returned HTTP {response.status_code}."
                )
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=503, 
                detail=f"Failed to connect to Reddit's network architecture: {str(e)}"
            )

    feed = feedparser.parse(response.content)
    
    mock_data = []
    for entry in feed.entries[:limit]:
        post_link = entry.get("link", "")
        
        post_document = {
            "title": entry.get("title", "No Title"),
            "author": entry.get("author", "Anonymous"),
            "link": post_link,
            "published_at": entry.get("published", ""),
            "summary_snippet": entry.get("summary", "")[:200] + "..." if "summary" in entry else "",
            "last_updated_in_db": datetime.utcnow().isoformat() + "Z",
            "feed_source": feed_type
        }

        if post_link:
            await posts_collection.update_one(
                {"link": post_link},
                {"$set": post_document},
                upsert=True
            )
            
        mock_data.append(post_document)
        
    return {
        "subreddit": "r/formula1",
        "feed_mode": feed_type,
        "fetched_and_stored_at": datetime.utcnow().isoformat() + "Z",
        "post_count": len(mock_data),
        "posts": mock_data
    }

@app.get("/")
async def root():
    return {
        "status": "Online",
        "message": "F1 RSS Ingestion & MongoDB pipeline ready. Open /docs to execute."
    }

@app.get("/f1-social-feed")
async def get_f1_feed(
    sort: str = Query(
        "hot", 
        regex="^(hot|new|top)$", 
        description="Select the sorting queue from the Swagger dropdown"
    ),
    limit: int = Query(
        5, 
        ge=1, 
        le=25, 
        description="Specify the maximum number of items to pull and parse"
    )
):
    """
    **Fetch & Sync F1 Community Threads**
    
    Pulls live data via RSS, saves/updates them seamlessly in MongoDB, 
    and returns the structured payload directly inside Swagger.
    """
    data = await fetch_and_store_rss(feed_type=sort, limit=limit)
    return data

@app.get("/stored-posts")
async def get_stored_posts(
    limit: int = Query(10, ge=1, le=100, description="Retrieve historical entries archived in Mongo")
):
    """
    **Retrieve Archived Database Entries**
    
    Directly queries your local MongoDB instance to check the historic posts 
    previously scraped by your platform endpoints.
    """
    cursor = posts_collection.find({}, {"_id": 0}).sort("last_updated_in_db", -1).limit(limit)
    stored_data = await cursor.to_list(length=limit)
    return {"database": "f1_platform", "collection": "reddit_posts", "records": stored_data}