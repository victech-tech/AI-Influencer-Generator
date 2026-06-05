import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "engagement.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS fetched_posts (
            tweet_id        TEXT PRIMARY KEY,
            author_handle   TEXT NOT NULL,
            author_name     TEXT,
            followers_count INTEGER,
            post_text       TEXT NOT NULL,
            post_url        TEXT,
            likes           INTEGER DEFAULT 0,
            retweets        INTEGER DEFAULT 0,
            reply_count     INTEGER DEFAULT 0,
            posted_at       DATETIME,
            fetched_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS suggestions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tweet_id        TEXT NOT NULL,
            run_date        DATE NOT NULL,
            rank            INTEGER NOT NULL,
            suggested_reply TEXT NOT NULL,
            selection_reason TEXT,
            telegram_sent   BOOLEAN DEFAULT FALSE,
            sent_at         DATETIME
        );

        CREATE TABLE IF NOT EXISTS runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
            posts_fetched   INTEGER,
            posts_selected  INTEGER,
            telegram_ok     BOOLEAN,
            error_msg       TEXT
        );
    """)
    conn.commit()
    conn.close()


def store_posts(posts: list[dict]):
    conn = get_connection()
    cur = conn.cursor()
    cur.executemany("""
        INSERT OR IGNORE INTO fetched_posts
            (tweet_id, author_handle, author_name, followers_count,
             post_text, post_url, likes, retweets, reply_count, posted_at)
        VALUES
            (:tweet_id, :author_handle, :author_name, :followers_count,
             :post_text, :post_url, :likes, :retweets, :reply_count, :posted_at)
    """, posts)
    conn.commit()
    conn.close()


def get_seen_tweet_ids() -> set[str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT tweet_id FROM fetched_posts")
    ids = {row[0] for row in cur.fetchall()}
    conn.close()
    return ids


def store_suggestions(suggestions: list[dict], run_date: str):
    conn = get_connection()
    cur = conn.cursor()
    for i, s in enumerate(suggestions, 1):
        cur.execute("""
            INSERT INTO suggestions (tweet_id, run_date, rank, suggested_reply, selection_reason)
            VALUES (?, ?, ?, ?, ?)
        """, (s["tweet_id"], run_date, i, s["suggested_reply"], s.get("reason", "")))
    conn.commit()
    conn.close()


def mark_suggestions_sent(run_date: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE suggestions SET telegram_sent = TRUE, sent_at = ?
        WHERE run_date = ?
    """, (datetime.utcnow().isoformat(), run_date))
    conn.commit()
    conn.close()


def log_run(posts_fetched: int, posts_selected: int, telegram_ok: bool, error_msg: str = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO runs (posts_fetched, posts_selected, telegram_ok, error_msg)
        VALUES (?, ?, ?, ?)
    """, (posts_fetched, posts_selected, telegram_ok, error_msg))
    conn.commit()
    conn.close()
