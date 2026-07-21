import feedparser
from datetime import datetime

from app.database import posts_collection
from bs4 import BeautifulSoup

from app.config import RSS_URL


class RedditRSSService:
    async def save_posts(self):

        posts = self.parse_feed()

        inserted = 0

        updated = 0

        for post in posts:

            post["updated_at"] = datetime.utcnow()

            result = await posts_collection.update_one(

                {"link": post["link"]},

                {

                    "$set": post

                },

                upsert=True

            )

            if result.upserted_id:

                inserted += 1

            else:

                updated += 1

        return {

            "inserted": inserted,

            "updated": updated

        }

    def fetch_feed(self):
        """
        Fetch Reddit RSS feed.
        """
        feed = feedparser.parse(RSS_URL)
        return feed


    def clean_html(self, html):

        if not html:
            return ""

        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator=" ", strip=True)


    def parse_feed(self):

        feed = self.fetch_feed()

        posts = []

        for entry in feed.entries:

            post = {

                "title": entry.get("title"),

                "author": entry.get("author"),

                "published": entry.get("published"),

                "summary": self.clean_html(
                    entry.get("summary", "")
                ),

                "link": entry.get("link")

            }

            posts.append(post)

        return posts