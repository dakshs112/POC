import asyncio

from app.reddit_service import RedditRSSService

service = RedditRSSService()

result = asyncio.run(service.save_posts())

print(result)