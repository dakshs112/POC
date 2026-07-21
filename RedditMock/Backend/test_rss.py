from pprint import pprint

from app.reddit_service import RedditRSSService

service = RedditRSSService()

posts = service.parse_feed()

print(f"Fetched {len(posts)} posts\n")

pprint(posts[0])