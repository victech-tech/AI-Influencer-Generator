#!/usr/bin/env python3
"""Main entry point — run once daily via cron."""

import logging
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import config
import db
import groq_client
import telegram_client
import x_scraper

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "engagement.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _send_alert(msg: str):
    """Send a plain error alert via Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        import requests
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": f"⚠️ X Engagement error:\n{msg}"},
                timeout=10,
            )
        except Exception:
            pass


def main():
    db.init_db()
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    posts_fetched = 0
    posts_selected = 0
    telegram_ok = False
    error_msg = None

    try:
        logger.info("Fetching following timeline via twscrape...")
        posts = x_scraper.fetch_following_timeline(
            lookback_hours=config.LOOKBACK_HOURS,
            max_posts=200,
        )
        logger.info(f"Fetched {len(posts)} posts before deduplication")

        # Deduplicate against DB
        seen_ids = db.get_seen_tweet_ids()
        posts = [p for p in posts if p.tweet_id not in seen_ids]
        logger.info(f"{len(posts)} new posts after deduplication")

        if not posts:
            msg = "No new posts found today — check your X login or following list."
            logger.warning(msg)
            _send_alert(msg)
            db.log_run(0, 0, False, msg)
            return

        # Apply follower filter
        posts = [p for p in posts if p.followers_count >= config.MIN_AUTHOR_FOLLOWERS]
        logger.info(f"{len(posts)} posts after follower filter (>={config.MIN_AUTHOR_FOLLOWERS})")

        # Store all fetched posts
        db.store_posts([{
            "tweet_id": p.tweet_id,
            "author_handle": p.author_handle,
            "author_name": p.author_name,
            "followers_count": p.followers_count,
            "post_text": p.post_text,
            "post_url": p.post_url,
            "likes": p.likes,
            "retweets": p.retweets,
            "reply_count": p.reply_count,
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
        } for p in posts])
        posts_fetched = len(posts)

        logger.info("Calling Groq to select best posts...")
        selected = groq_client.select_posts(posts)
        logger.info(f"Groq selected {len(selected)} posts")

        logger.info("Calling Groq to draft replies...")
        suggestions = groq_client.draft_replies(posts, selected)
        posts_selected = len(suggestions)
        logger.info(f"Got {posts_selected} reply drafts")

        db.store_suggestions(suggestions, run_date)

        post_lookup = {p.tweet_id: p for p in posts}
        logger.info("Sending Telegram brief...")
        telegram_ok = telegram_client.send_daily_brief(suggestions, post_lookup)

        if telegram_ok:
            db.mark_suggestions_sent(run_date)
            logger.info("Daily brief sent successfully.")
        else:
            error_msg = "Telegram send failed after retries"
            logger.error(error_msg)
            _send_alert(error_msg)

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Fatal error: {e}")
        _send_alert(f"Fatal error in run_daily.py:\n{e}")

    finally:
        db.log_run(posts_fetched, posts_selected, telegram_ok, error_msg)


if __name__ == "__main__":
    main()
