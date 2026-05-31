"""
PullPush.io integration.

PullPush is the community continuation of Pushshift — the most comprehensive
Reddit archive ever built (posts and comments back to 2005). While the original
Pushshift was restricted, PullPush provides the same API surface for historical
research.

API: https://pullpush.io
No authentication required.

Combined with Arctic Shift, this gives Argus complete historical Reddit coverage:
- Arctic Shift: recent data, full-text search
- PullPush: historical depth, date-range queries, author lookups
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from .models import RawSignal

log = logging.getLogger(__name__)

BASE = "https://api.pullpush.io/reddit/search"
HEADERS = {
    "User-Agent": "argus-personal/0.1 (https://github.com/makhskham/argus)",
}


async def _get(client: httpx.AsyncClient, url: str, params: dict) -> dict | None:
    try:
        r = await client.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.warning("pullpush HTTP %d: %s", e.response.status_code, url)
        return None
    except Exception as e:
        log.warning("pullpush error: %s", e)
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
        post_id = post.get("id", "")
        return RawSignal(
            source=f"r/{subreddit}",
            source_type="reddit",
            external_id=f"pp_{post_id}",
            subreddit=subreddit,
            author=post.get("author", "[deleted]"),
            title=post.get("title"),
            body=body[:8000],
            url=f"https://reddit.com{post.get('permalink', f'/r/{subreddit}/comments/{post_id}/')}",
            upvotes=int(post.get("score", 0)),
            upvote_ratio=float(post.get("upvote_ratio", 0)),
            posted_at=posted_at,
        )
    except Exception:
        return None


def _comment_to_signal(comment: dict) -> RawSignal | None:
    try:
        body = comment.get("body", "")
        if not body or body in ("[deleted]", "[removed]") or len(body) < 40:
            return None
        subreddit = comment.get("subreddit", "")
        link_id = comment.get("link_id", "").replace("t3_", "")
        comment_id = comment.get("id", "")
        created = comment.get("created_utc")
        posted_at = (
            datetime.fromtimestamp(float(created), tz=timezone.utc)
            if created else datetime.now(tz=timezone.utc)
        )
        return RawSignal(
            source=f"r/{subreddit}",
            source_type="reddit",
            external_id=f"pp_c_{comment_id}",
            subreddit=subreddit,
            author=comment.get("author", "[deleted]"),
            body=body[:4000],
            url=f"https://reddit.com/r/{subreddit}/comments/{link_id}/_/{comment_id}",
            upvotes=int(comment.get("score", 0)),
            upvote_ratio=0.0,
            posted_at=posted_at,
        )
    except Exception:
        return None


async def search_posts(
    q: str = "",
    subreddit: str = "",
    author: str = "",
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    sort: str = "score",
    sort_type: str = "score",
    limit: int = 100,
) -> list[dict]:
    """Raw search against PullPush post archive. Returns raw dicts."""
    params: dict = {"size": min(limit, 100), "sort": sort, "sort_type": sort_type}
    if q:
        params["q"] = q
    if subreddit:
        params["subreddit"] = subreddit
    if author:
        params["author"] = author
    if after:
        params["after"] = int(after.timestamp())
    if before:
        params["before"] = int(before.timestamp())

    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/submission", params)
        return data.get("data", []) if data else []


async def search_comments(
    q: str = "",
    subreddit: str = "",
    author: str = "",
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    sort: str = "score",
    limit: int = 100,
) -> list[dict]:
    """Raw search against PullPush comment archive. Returns raw dicts."""
    params: dict = {"size": min(limit, 100), "sort": sort}
    if q:
        params["q"] = q
    if subreddit:
        params["subreddit"] = subreddit
    if author:
        params["author"] = author
    if after:
        params["after"] = int(after.timestamp())
    if before:
        params["before"] = int(before.timestamp())

    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/comment", params)
        return data.get("data", []) if data else []


async def search_ticker_history(
    ticker: str,
    days_back: int = 30,
    limit: int = 100,
) -> list[RawSignal]:
    """
    Search PullPush for historical mentions of a ticker.
    Useful for understanding how long a stock has been discussed
    and whether it truly is an early discovery.
    """
    signals: list[RawSignal] = []
    after = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    posts_raw = await search_posts(
        q=f"${ticker} OR \"{ticker}\"", after=after, limit=limit
    )
    for p in posts_raw:
        s = _post_to_signal(p)
        if s:
            signals.append(s)

    await asyncio.sleep(0.5)

    comments_raw = await search_comments(
        q=f"${ticker} OR \"{ticker}\"", after=after, limit=limit
    )
    for c in comments_raw:
        s = _comment_to_signal(c)
        if s:
            signals.append(s)

    log.info("pullpush %s (%dd): %d signals", ticker, days_back, len(signals))
    return signals


async def search_niche_discovery(days_back: int = 3) -> list[RawSignal]:
    """Search PullPush for investment discovery signals from the past few days."""
    signals: list[RawSignal] = []
    after = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    queries = [
        "hidden gem undervalued small cap",
        "micro cap no coverage",
        "before it blows up stock ticker",
    ]

    async with httpx.AsyncClient() as client:
        for q in queries:
            await asyncio.sleep(1)
            params = {
                "q": q,
                "after": int(after.timestamp()),
                "size": 25,
                "sort": "score",
            }
            post_data = await _get(client, f"{BASE}/submission", params)
            if post_data:
                for p in post_data.get("data", []):
                    s = _post_to_signal(p)
                    if s:
                        signals.append(s)

            await asyncio.sleep(0.5)
            comment_data = await _get(client, f"{BASE}/comment", params)
            if comment_data:
                for c in comment_data.get("data", []):
                    s = _comment_to_signal(c)
                    if s:
                        signals.append(s)

    log.info("pullpush discovery: %d signals", len(signals))
    return signals
