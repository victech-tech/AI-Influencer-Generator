import json
import os
import time
import logging

from groq import Groq

import config
from prompts import (
    SELECTION_SYSTEM, SELECTION_USER_TEMPLATE,
    DRAFTING_SYSTEM, DRAFTING_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)


def _get_client() -> Groq:
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


def _call_groq(client: Groq, system: str, user: str, retries: int = 2) -> dict:
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.3,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"Groq call failed (attempt {attempt + 1}): {e}. Retrying in 60s.")
                time.sleep(60)
            else:
                raise


def _posts_to_json(posts) -> str:
    data = []
    for p in posts:
        data.append({
            "tweet_id": p.tweet_id if hasattr(p, "tweet_id") else p["tweet_id"],
            "author_handle": p.author_handle if hasattr(p, "author_handle") else p["author_handle"],
            "author_name": p.author_name if hasattr(p, "author_name") else p.get("author_name", ""),
            "followers_count": p.followers_count if hasattr(p, "followers_count") else p.get("followers_count", 0),
            "post_text": p.post_text if hasattr(p, "post_text") else p["post_text"],
            "reply_count": p.reply_count if hasattr(p, "reply_count") else p.get("reply_count", 0),
            "likes": p.likes if hasattr(p, "likes") else p.get("likes", 0),
            "posted_at": str(p.posted_at if hasattr(p, "posted_at") else p.get("posted_at", "")),
        })
    return json.dumps(data, ensure_ascii=False)


def select_posts(posts) -> list[dict]:
    """Returns list of {tweet_id, reason} dicts for the top N posts."""
    client = _get_client()
    system = SELECTION_SYSTEM.format(
        topic_interests=", ".join(config.TOPIC_INTERESTS),
        max_replies=config.MAX_EXISTING_REPLIES,
    )
    user = SELECTION_USER_TEMPLATE.format(
        topic_interests=", ".join(config.TOPIC_INTERESTS),
        max_replies=config.MAX_EXISTING_REPLIES,
        min_followers=config.MIN_AUTHOR_FOLLOWERS,
        posts_json=_posts_to_json(posts),
    )
    result = _call_groq(client, system, user)
    return result.get("selected", [])


def draft_replies(posts, selected: list[dict]) -> list[dict]:
    """Returns list of {tweet_id, suggested_reply, reason} dicts."""
    client = _get_client()

    # Build lookup for post data
    post_lookup = {}
    for p in posts:
        pid = p.tweet_id if hasattr(p, "tweet_id") else p["tweet_id"]
        post_lookup[pid] = p

    selected_ids = {s["tweet_id"] for s in selected}
    selected_posts = [p for p in posts if (p.tweet_id if hasattr(p, "tweet_id") else p["tweet_id"]) in selected_ids]

    system = DRAFTING_SYSTEM
    user = DRAFTING_USER_TEMPLATE.format(posts_json=_posts_to_json(selected_posts))
    result = _call_groq(client, system, user)
    replies = result.get("replies", [])

    # Merge reasons from selection into replies
    reason_lookup = {s["tweet_id"]: s.get("reason", "") for s in selected}
    for r in replies:
        r["reason"] = reason_lookup.get(r["tweet_id"], "")

    return replies
