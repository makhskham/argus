"""
Arctic Shift integration.

Arctic Shift (https://github.com/ArthurHeitmann/arctic_shift) is a
community-maintained archive of all public Reddit data, built by
Arthur Heitmann. It provides a free API for searching the complete
Reddit history — every post and comment ever made on public subreddits.

This is the core of Argus's hidden gem detection. A company discussed
in r/ChemicalEngineering in January might not hit r/wallstreetbets until
March. Arctic Shift lets us find it in January.

API base: https://arctic-shift.photon-reddit.com/api
API docs: https://arctic-shift.photon-reddit.com/api-docs
GitHub:   https://github.com/ArthurHeitmann/arctic_shift

No authentication required. Rate limit: ~60 requests/minute.
Self-hosting is possible with the full Reddit data dump for even higher
throughput — see the Arctic Shift README for setup instructions.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from .models import RawSignal

log = logging.getLogger(__name__)

BASE = "https://arctic-shift.photon-reddit.com/api"
HEADERS = {
    "User-Agent": "argus-personal/0.1 (https://github.com/makhskham/argus)",
}

# Discovery phrases — searched across ALL of Reddit to surface niche signals
DISCOVERY_QUERIES = [
    "no one is talking about stock",
    "hidden gem small cap",
    "under the radar ticker",
    "before it blows up stock",
    "DD due diligence undervalued",
    "catalyst upcoming earnings",
    "short squeeze potential",
    "micro cap discovery",
]


async def _get(client: httpx.AsyncClient, url: str, params: dict) -> dict | None:
    try:
        r = await client.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        log.warning("arctic shift HTTP %d: %s", e.response.status_code, url)
        return None
    except Exception as e:
        log.warning("arctic shift error %s: %s", url, e)
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
    except Exception:
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
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────
# Core query functions (used by both the scraper and the manual UI)
# ──────────────────────────────────────────────────────────────────

async def query_posts(
    q: str = "",
    subreddit: str = "",
    author: str = "",
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    sort: str = "score",
    limit: int = 100,
    min_score: int = 0,
) -> list[dict]:
    """
    Raw query against Arctic Shift post archive.
    Returns raw dicts (not RawSignal) so the UI can display full metadata.
    """
    params: dict = {"limit": min(limit, 100), "sort": sort}
    if q:
        params["q"] = q
    if subreddit:
        params["subreddit"] = subreddit
    if author:
        params["author"] = author
    if after:
        # Arctic Shift expects Unix timestamp integer
        params["after"] = str(int(after.timestamp()))
    if before:
        params["before"] = str(int(before.timestamp()))

    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/posts/search", params)
        if not data:
            return []
        results = data.get("data", [])
        if min_score:
            results = [p for p in results if int(p.get("score", 0)) >= min_score]
        return results


async def query_comments(
    q: str = "",
    subreddit: str = "",
    author: str = "",
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    sort: str = "score",
    limit: int = 100,
    min_score: int = 0,
) -> list[dict]:
    """
    Raw query against Arctic Shift comment archive.
    Returns raw dicts so the UI can display full metadata.
    """
    params: dict = {"limit": min(limit, 100), "sort": sort}
    if q:
        params["q"] = q
    if subreddit:
        params["subreddit"] = subreddit
    if author:
        params["author"] = author
    if after:
        params["after"] = str(int(after.timestamp()))
    if before:
        params["before"] = str(int(before.timestamp()))

    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/comments/search", params)
        if not data:
            return []
        results = data.get("data", [])
        if min_score:
            results = [c for c in results if int(c.get("score", 0)) >= min_score]
        return results


async def get_post_comments_by_id(post_id: str, limit: int = 500) -> list[dict]:
    """Get all comments for a post by its Reddit ID."""
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/comments", {
            "link_id": f"t3_{post_id}",
            "limit": limit,
            "sort": "score",
        })
        return data.get("data", []) if data else []


async def get_user_posts(username: str, limit: int = 50) -> list[dict]:
    """Get posts by a specific Reddit user (useful for tracking Trusted Voices)."""
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/posts/search", {
            "author": username,
            "limit": limit,
            "sort": "score",
        })
        return data.get("data", []) if data else []


async def get_user_comments(username: str, limit: int = 100) -> list[dict]:
    """Get comments by a specific Reddit user."""
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{BASE}/comments/search", {
            "author": username,
            "limit": limit,
            "sort": "score",
        })
        return data.get("data", []) if data else []


# ──────────────────────────────────────────────────────────────────
# Signal-returning wrappers (for the scrape pipeline)
# ──────────────────────────────────────────────────────────────────

async def search_posts_for_ticker(
    ticker: str,
    days_back: int = 7,
    limit: int = 100,
) -> list[RawSignal]:
    """Search ALL of Reddit for a specific ticker symbol — posts."""
    after = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
    raw = await query_posts(q=f"${ticker} OR \"{ticker}\"", after=after, limit=limit)
    return [s for s in (_post_to_signal(p) for p in raw) if s]


async def search_comments_for_ticker(
    ticker: str,
    days_back: int = 7,
    limit: int = 200,
) -> list[RawSignal]:
    """Search ALL Reddit comments for a specific ticker symbol."""
    after = datetime.now(tz=timezone.utc) - timedelta(days=days_back)
    raw = await query_comments(q=f"${ticker} OR \"{ticker}\"", after=after, limit=limit)
    return [s for s in (_comment_to_signal(c) for c in raw) if s]


async def search_investment_signals(days_back: int = 30) -> list[RawSignal]:
    """
    Search across ALL of Reddit for investment discovery phrases.
    Note: Arctic Shift is a historical archive - no date filter used since
    recent data (2025-2026) may not be indexed yet. Gets top-scored results.
    """
    signals: list[RawSignal] = []

    async with httpx.AsyncClient() as client:
        for query in DISCOVERY_QUERIES:
            await asyncio.sleep(1)

            # No date filter - let Arctic Shift return its best results
            post_data = await _get(client, f"{BASE}/posts/search", {
                "q": query, "limit": 25, "sort": "score",
            })
            if post_data:
                for p in post_data.get("data", []):
                    s = _post_to_signal(p)
                    if s:
                        signals.append(s)

            await asyncio.sleep(0.5)

            comment_data = await _get(client, f"{BASE}/comments/search", {
                "q": query, "limit": 50, "sort": "score",
            })
            if comment_data:
                for c in comment_data.get("data", []):
                    s = _comment_to_signal(c)
                    if s:
                        signals.append(s)

    log.info("arctic shift discovery: %d signals across all Reddit", len(signals))
    return signals
