from app.database import posts_collection
from app.database import posts_collection
from app.utils import serialize_documents


class AnalyticsService:

    async def get_stats(self):

        total_posts = await posts_collection.count_documents({})

        unique_authors = len(
            await posts_collection.distinct("author")
        )

        latest_post = await posts_collection.find_one(
            {},
            sort=[("updated_at", -1)]
        )

        return {

            "total_posts": total_posts,

            "unique_authors": unique_authors,

            "last_updated": latest_post["updated_at"] if latest_post else None

        }


    async def get_posts(self, limit: int = 20):

        cursor = posts_collection.find().sort(
            "published",
            -1
        )

        posts = await cursor.to_list(length=limit)

        for post in posts:
            post["_id"] = str(post["_id"])

        return posts


    async def get_top_authors(self):

        pipeline = [

            {

                "$group":{

                    "_id":"$author",

                    "posts":{"$sum":1}

                }

            },

            {

                "$sort":{

                    "posts":-1

                }

            }

        ]

        cursor = posts_collection.aggregate(pipeline)

        return await cursor.to_list(length=20)


    async def get_posts_timeline(self):

        pipeline = [

            {

                "$group":{

                    "_id":"$published",

                    "count":{"$sum":1}

                }

            },

            {

                "$sort":{

                    "_id":1

                }

            }

        ]

        cursor = posts_collection.aggregate(pipeline)

        return await cursor.to_list(length=100)
