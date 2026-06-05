#!/usr/bin/env python3
"""One-time setup: register your X account with twscrape."""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import twscrape

ACCOUNTS_DB = os.path.join(os.path.dirname(__file__), "data", "accounts.db")


async def setup():
    username = os.getenv("X_USERNAME")
    password = os.getenv("X_PASSWORD")
    email = os.getenv("X_EMAIL")
    email_password = os.getenv("X_EMAIL_PASSWORD")

    missing = [k for k, v in {
        "X_USERNAME": username,
        "X_PASSWORD": password,
        "X_EMAIL": email,
        "X_EMAIL_PASSWORD": email_password,
    }.items() if not v]

    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        print("Fill in your .env file and re-run setup.py")
        sys.exit(1)

    os.makedirs(os.path.dirname(ACCOUNTS_DB), exist_ok=True)
    api = twscrape.API(ACCOUNTS_DB)

    print(f"Adding account @{username}...")
    await api.pool.add_account(
        username=username,
        password=password,
        email=email,
        email_password=email_password,
    )

    print("Logging in (may take 10–30 seconds)...")
    await api.pool.login_all()
    print("✅ Account added and logged in successfully.")
    print(f"Session stored in: {ACCOUNTS_DB}")
    print("\nNext step: run `python run_daily.py` to test the full pipeline.")


if __name__ == "__main__":
    asyncio.run(setup())
