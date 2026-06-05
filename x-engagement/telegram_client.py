import os
import time
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send_message(token: str, chat_id: str, text: str, retries: int = 3) -> bool:
    url = TELEGRAM_API.format(token=token)
    for attempt in range(retries):
        try:
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }, timeout=15)
            if resp.status_code == 200:
                return True
            logger.warning(f"Telegram HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"Telegram send error (attempt {attempt + 1}): {e}")
        if attempt < retries - 1:
            time.sleep(10)
    return False


def _format_age(posted_at) -> str:
    if posted_at is None:
        return "?"
    now = datetime.now(timezone.utc)
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    diff = now - posted_at
    hours = int(diff.total_seconds() / 3600)
    if hours < 1:
        mins = int(diff.total_seconds() / 60)
        return f"{mins}m ago"
    return f"{hours}h ago"


def _format_number(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def send_daily_brief(suggestions: list[dict], post_lookup: dict) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    today = datetime.now(timezone.utc).strftime("%A %-d %b %Y")
    total_scanned = len(post_lookup)

    header = (
        f"🤖 *X Engagement Brief — {today}*\n\n"
        f"Scanned {total_scanned} posts from people you follow.\n"
        f"Here are today's {len(suggestions)} best reply opportunities 👇"
    )
    _send_message(token, chat_id, header)
    time.sleep(1)

    for i, s in enumerate(suggestions, 1):
        post = post_lookup.get(s["tweet_id"])
        if not post:
            continue

        author_handle = post.author_handle if hasattr(post, "author_handle") else post["author_handle"]
        author_name = post.author_name if hasattr(post, "author_name") else post.get("author_name", "")
        followers = post.followers_count if hasattr(post, "followers_count") else post.get("followers_count", 0)
        post_text = post.post_text if hasattr(post, "post_text") else post["post_text"]
        post_url = post.post_url if hasattr(post, "post_url") else post.get("post_url", "")
        likes = post.likes if hasattr(post, "likes") else post.get("likes", 0)
        retweets = post.retweets if hasattr(post, "retweets") else post.get("retweets", 0)
        reply_count = post.reply_count if hasattr(post, "reply_count") else post.get("reply_count", 0)
        posted_at = post.posted_at if hasattr(post, "posted_at") else post.get("posted_at")

        truncated = post_text[:220] + ("..." if len(post_text) > 220 else "")
        reply_text = s.get("suggested_reply", "")
        reason = s.get("reason", "")

        card = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Post {i} of {len(suggestions)}*\n\n"
            f"👤 @{author_handle} · {_format_number(followers)} followers\n"
            f"🕐 {_format_age(posted_at)}  ❤️ {likes}  💬 {reply_count}  🔁 {retweets}\n\n"
            f"📝 *Original:*\n\"{truncated}\"\n\n"
            f"🔗 {post_url}\n\n"
            f"💡 *Suggested Reply:*\n\"{reply_text}\"\n\n"
            f"📋 *Why:* {reason}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        ok = _send_message(token, chat_id, card)
        if not ok:
            logger.error(f"Failed to send card {i}")
        time.sleep(1)

    footer = (
        "✅ That's all for today.\n"
        "Review above, then post your favourites manually on X.\n"
        "Good luck growing! 🚀"
    )
    _send_message(token, chat_id, footer)
    return True
