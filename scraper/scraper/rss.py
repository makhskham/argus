"""
Reddit RSS feed scraper.

Reddit explicitly supports and maintains RSS feeds for every public subreddit.
No credentials, no API key, no rate limit concerns.

RSS feed URLs (all public, no auth):
  New posts:  https://www.reddit.com/r/{sub}/new/.rss
  Hot posts:  https://www.reddit.com/r/{sub}/hot/.rss
  Top (week): https://www.reddit.com/r/{sub}/top/.rss?t=week
  Top posts per user: https://www.reddit.com/user/{user}/submitted/.rss

RSS advantages over JSON API:
- Much more lenient rate limits (Reddit explicitly intends these to be polled)
- New posts appear here as soon as published (real-time monitoring)
- Stable and officially maintained by Reddit
- Works on old.reddit.com too: https://old.reddit.com/r/{sub}/new/.rss

RSS limitation: post-level only (no comments). Use the JSON API for comments
on posts that look interesting.
"""
import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser  # type: ignore
import httpx

from .models import RawSignal

log = logging.getLogger(__name__)

UA = "argus-personal/0.1 (https://github.com/makhskham/argus)"

# All subreddits to monitor via RSS
SUBREDDITS = [
    # Mainstream investment communities
    "investing", "stocks", "StockMarket", "Bogleheads", "dividends",
    "ValueInvesting", "SecurityAnalysis", "wallstreetbets", "Options",
    "Daytrading", "CanadianInvestor", "algotrading", "thetagang",
    # Small cap and niche — the hidden gem sources
    "pennystocks", "Superstonk", "smallcap", "RobinhoodPennyStocks",
    "undervalued", "MicroCapStocks", "OTCstocks", "investing_discussion",
    "weedstocks", "EVstocks", "stocks_advice", "stockmarketnews",
]


def _parse_entry(entry: dict, subreddit: str) -> RawSignal | None:
    """Parse a single RSS feed entry into a RawSignal."""
    try:
        title = entry.get("title", "")
        # RSS summary contains HTML - strip it to get the text body
        summary_html = entry.get("summary", "")

        # Simple HTML strip using lxml or fallback
        body = title
        if summary_html:
            try:
                from lxml.html import fromstring
                doc = fromstring(summary_html)
                text = doc.text_content().strip()
                if text and len(text) > len(title):
                    body = text
            except Exception:
                body = summary_html.replace("<p>", "\n").replace("</p>", "")
                body = "".join(c for c in body if c not in "<>").strip()

        body = body[:6000]
        if not body:
            return None

        # Parse published date
        published = entry.get("published") or entry.get("updated")
        posted_at = datetime.now(tz=timezone.utc)
        if published:
            try:
                posted_at = parsedate_to_datetime(published)
            except Exception:
                pass

        # Extract post ID from the link
        link = entry.get("link", "")
        # Reddit RSS links look like: https://www.reddit.com/r/sub/comments/abc123/title/
        parts = link.rstrip("/").split("/")
        post_id = ""
        if "comments" in parts:
            idx = parts.index("comments")
            if idx + 1 < len(parts):
                post_id = parts[idx + 1]

        external_id = f"rss_{post_id}" if post_id else f"rss_{hash(link)}"
        author = entry.get("author", "[unknown]").replace("/u/", "").replace("u/", "")

        return RawSignal(
            source=f"r/{subreddit}",
            source_type="reddit",
            external_id=external_id,
            subreddit=subreddit,
            author=author,
            title=title,
            body=body,
            url=link,
            upvotes=0,  # RSS doesn't include vote counts
            upvote_ratio=0.0,
            posted_at=posted_at,
        )
    except Exception as e:
        log.debug("rss entry parse error: %s", e)
        return None


async def scrape_subreddit_rss(
    subreddit: str,
    feed_type: str = "new",
    time_filter: str = "week",
) -> list[RawSignal]:
    """
    Scrape a subreddit via its RSS feed.

    feed_type: "new" (real-time), "hot" (trending), or "top"
    time_filter: for "top" feeds - "day", "week", "month", "year", "all"
    """
    if feed_type == "top":
        url = f"https://www.reddit.com/r/{subreddit}/top/.rss?t={time_filter}"
    else:
        url = f"https://www.reddit.com/r/{subreddit}/{feed_type}/.rss"

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers={"User-Agent": UA}, timeout=20)
            r.raise_for_status()
            content = r.text
    except Exception as e:
        log.warning("rss fetch failed r/%s: %s", subreddit, e)
        return []

    # feedparser is synchronous — run in thread pool
    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, content)

    signals = []
    for entry in feed.entries:
        sig = _parse_entry(entry, subreddit)
        if sig:
            signals.append(sig)

    return signals


async def scrape_subreddit_rss_combined(subreddit: str) -> list[RawSignal]:
    """Get both new (real-time) and top weekly posts via RSS."""
    new_sigs, top_sigs = await asyncio.gather(
        scrape_subreddit_rss(subreddit, "new"),
        scrape_subreddit_rss(subreddit, "top", "week"),
        return_exceptions=True,
    )
    combined = []
    if isinstance(new_sigs, list):
        combined.extend(new_sigs)
    if isinstance(top_sigs, list):
        combined.extend(top_sigs)
    return combined


async def scrape_all_rss(batch_size: int = 6) -> list[RawSignal]:
    """
    Scrape all tracked subreddits via RSS in batches.
    More reliable than JSON for new post detection.
    """
    all_signals: list[RawSignal] = []

    for i in range(0, len(SUBREDDITS), batch_size):
        batch = SUBREDDITS[i:i + batch_size]
        tasks = [scrape_subreddit_rss_combined(sub) for sub in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_signals.extend(r)
        if i + batch_size < len(SUBREDDITS):
            await asyncio.sleep(1)

    log.info("rss: %d signals from %d subreddits", len(all_signals), len(SUBREDDITS))
    return all_signals


async def monitor_user_rss(username: str) -> list[RawSignal]:
    """Get recent posts by a specific user via their RSS feed. Useful for Trusted Voices."""
    url = f"https://www.reddit.com/user/{username}/submitted/.rss"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers={"User-Agent": UA}, timeout=20)
            r.raise_for_status()
            content = r.text
    except Exception as e:
        log.warning("rss user fetch failed u/%s: %s", username, e)
        return []

    loop = asyncio.get_event_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, content)

    signals = []
    for entry in feed.entries:
        sig = _parse_entry(entry, "user_feed")
        if sig:
            sig.author = username
            signals.append(sig)

    return signals
