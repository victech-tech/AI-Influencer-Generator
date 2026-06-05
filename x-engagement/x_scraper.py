import asyncio
import os
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

import twscrape

ACCOUNTS_DB = os.path.join(os.path.dirname(__file__), "data", "accounts.db")


@dataclass
class Post:
    tweet_id: str
    author_handle: str
    author_name: str
    followers_count: int
    post_text: str
    post_url: str
    likes: int
    retweets: int
    reply_count: int
    posted_at: datetime


async def _fetch(lookback_hours: int, max_posts: int) -> list[Post]:
    api = twscrape.API(ACCOUNTS_DB)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    posts = []

    async for tweet in api.following_timeline(limit=max_posts):
        # Skip retweets
        if tweet.retweetedTweet is not None:
            continue
        if tweet.rawContent.startswith("RT @"):
            continue
        # Skip posts older than lookback window
        tweet_date = tweet.date
        if tweet_date.tzinfo is None:
            tweet_date = tweet_date.replace(tzinfo=timezone.utc)
        if tweet_date < cutoff:
            continue

        posts.append(Post(
            tweet_id=str(tweet.id),
            author_handle=tweet.user.username,
            author_name=tweet.user.displayname,
            followers_count=tweet.user.followersCount or 0,
            post_text=tweet.rawContent,
            post_url=tweet.url,
            likes=tweet.likeCount or 0,
            retweets=tweet.retweetCount or 0,
            reply_count=tweet.replyCount or 0,
            posted_at=tweet_date,
        ))

    return posts


def fetch_following_timeline(lookback_hours: int = 24, max_posts: int = 200) -> list[Post]:
    return asyncio.run(_fetch(lookback_hours, max_posts))
