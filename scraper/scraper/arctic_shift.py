"""
Arctic Shift API scraper.

Arctic Shift is a community-maintained archive of all public Reddit data.
It lets us search across ALL of Reddit by ticker symbol, finding mentions
in obscure subreddits we'd never think to monitor manually.

API docs: https://arctic-shift.photon-reddit.com/api-docs
No authentication required. Rate limit: ~60 requests/minute.

This is the key to hidden gem detection — a stock being discussed in
r/ChemicalEngineering or r/biotech before r/wallstreetbets ever hears of it.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from .models import RawSignal

log = logging.getLogger(__name__)

BASE = "https://arctic-shift.photon-reddit.com/api"
HEADERS = {"User-Agent": "argus-personal/0.1"}

# Investment-related search terms we'll use to find signals
# The scraper searches for these across ALL of Reddit
SEARCH_QUERIES = [
    # Direct investment signals
    "due diligence", "DD", "bull thesis", "bear thesis",
    "price target", "undervalued", "hidden gem", "small cap",
    "going to moon", "short squeeze", "catalyst", "earnings beat",
    # Event-driven signals
    "acquisition", "merger", "partnership deal", "FDA approval",
    "contract win", "revenue growth", "beat estimates",
    # Niche discovery signals
    "no one is talking about", "overlooked stock", "under the radar",
    "micro cap", "penny stock gem", "before it blows up",
]


async def _get(client: httpx.AsyncClient, url: str, params: dict) -> dict | None:
    try:
        r = await client.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.warning("arctic shift %s status %d", url, e.response.status_code)
        return None
    except Exception as e:
        log.warning("arctic shift %s error: %s", url, e)
        return None


def _post_to_signal(post: dict) -> RawSignal | None:
    try:
        body = post.get("selftext") or post.get("title") or ""
        if not body or body in ("[deleted]", "[removed]"):
            return None
        subreddit = post.get("subreddit", "")
        created = post.get("created_utc")
        posted_at = (
            datetime.fromtimestamp(float(created), tz=timezone.utc)
            if created else datetime.now(tz=timezone.utc)
        )
        return RawSignal(
            source=f"r/{subreddit}",
            source_type="reddit",
            external_id=post.get("id", ""),
            subreddit=subreddit,
            author=post.get("author", "[deleted]"),
            title=post.get("title"),
            body=body[:8000],
            url=f"https://reddit.com{post.get('permalink', '')}",
            upvotes=int(post.get("score", 0)),
            upvote_ratio=float(post.get("upvote_ratio", 0)),
            posted_at=posted_at,
        )
    except Exception as e:
        log.debug("post parse error: %s", e)
        return None


def _comment_to_signal(comment: dict) -> RawSignal | None:
    try:
        body = comment.get("body", "")
        if not body or body in ("[deleted]", "[removed]") or len(body) < 40:
            return None
        subreddit = comment.get("subreddit", "")
        link_id = comment.get("link_id", "").replace("t3_", "")
        created = comment.get("created_utc")
        posted_at = (
            datetime.fromtimestamp(float(created), tz=timezone.utc)
            if created else datetime.now(tz=timezone.utc)
        )
        return RawSignal(
            source=f"r/{subreddit}",
            source_type="reddit",
            external_id=f"c_{comment.get('id', '')}",
            subreddit=subreddit,
            author=comment.get("author", "[deleted]"),
            body=body[:4000],
            url=f"https://reddit.com/r/{subreddit}/comments/{link_id}/_/{comment.get('id', '')}",
            upvotes=int(comment.get("score", 0)),
            upvote_ratio=0.0,
            posted_at=posted_at,
        )
    except Exception as e:
        log.debug("comment parse error: %s", e)
        return None


async def search_posts_for_ticker(
    ticker: str,
    days_back: int = 7,
    limit: int = 100,
) -> list[RawSignal]:
    """Search ALL of Reddit for a specific ticker symbol."""
    signals: list[RawSignal] = []
    after = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/posts/search", {
            "q": f"${ticker} OR \"{ticker}\"",
            "limit": limit,
            "after": after.isoformat(),
            "sort": "score",
        })
        if not data:
            return signals

        for post in data.get("data", []):
            sig = _post_to_signal(post)
            if sig:
                signals.append(sig)

    return signals


async def search_comments_for_ticker(
    ticker: str,
    days_back: int = 7,
    limit: int = 200,
) -> list[RawSignal]:
    """Search ALL Reddit comments for a specific ticker symbol."""
    signals: list[RawSignal] = []
    after = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/comments/search", {
            "q": f"${ticker} OR \"{ticker}\"",
            "limit": limit,
            "after": after.isoformat(),
            "sort": "score",
        })
        if not data:
            return signals

        for comment in data.get("data", []):
            sig = _comment_to_signal(comment)
            if sig:
                signals.append(sig)

    return signals


async def search_investment_signals(days_back: int = 1) -> list[RawSignal]:
    """
    Search across ALL of Reddit for investment-related discussions.
    This catches signals from subreddits we don't explicitly track.
    Focuses on discovery phrases that indicate someone found something early.
    """
    signals: list[RawSignal] = []
    after = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    async with httpx.AsyncClient() as client:
        # Run a few high-value search queries
        priority_queries = [
            "no one is talking about stock",
            "hidden gem small cap",
            "before it blows up ticker",
            "under the radar stock",
            "DD due diligence undervalued",
        ]

        for query in priority_queries:
            await asyncio.sleep(1)  # respect rate limit

            # Search posts
            post_data = await _get(client, f"{BASE}/posts/search", {
                "q": query,
                "limit": 25,
                "after": after.isoformat(),
                "sort": "score",
            })
            if post_data:
                for post in post_data.get("data", []):
                    sig = _post_to_signal(post)
                    if sig:
                        signals.append(sig)

            await asyncio.sleep(0.5)

            # Search comments
            comment_data = await _get(client, f"{BASE}/comments/search", {
                "q": query,
                "limit": 50,
                "after": after.isoformat(),
                "sort": "score",
            })
            if comment_data:
                for comment in comment_data.get("data", []):
                    sig = _comment_to_signal(comment)
                    if sig:
                        signals.append(sig)

    log.info("arctic shift discovery: found %d signals across all Reddit", len(signals))
    return signals


async def get_post_comments(post_id: str, subreddit: str) -> list[RawSignal]:
    """Get all comments for a specific post."""
    signals: list[RawSignal] = []
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/comments", {
            "link_id": f"t3_{post_id}",
            "limit": 500,
            "sort": "score",
        })
        if not data:
            return signals
        for comment in data.get("data", []):
            sig = _comment_to_signal(comment)
            if sig:
                signals.append(sig)
    return signals
