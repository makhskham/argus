"""
Reddit scraper with two modes:
- Public JSON API (no credentials needed) - works immediately
- PRAW (requires Reddit API credentials) - more reliable, higher rate limits

The scraper automatically uses PRAW if credentials are configured,
and falls back to the public JSON API otherwise.
"""
import asyncio
import logging
import re
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from .models import RawSignal

log = logging.getLogger(__name__)

# All investment subreddits — large caps + small cap / niche communities
SUBREDDITS = [
    # Large/mainstream
    "investing", "stocks", "StockMarket", "Bogleheads", "dividends",
    "ValueInvesting", "SecurityAnalysis", "wallstreetbets", "Options",
    "Daytrading", "CanadianInvestor", "algotrading", "thetagang",
    # Small cap / niche / emerging — hidden gem detection
    "pennystocks", "Superstonk", "smallcap", "RobinhoodPennyStocks",
    "ValueInvestingAndMore", "MicroCapStocks", "OTC_Stocks", "investing_discussion",
    "weedstocks", "EVstocks", "stocks_advice", "stockmarketnews",
    # Halal / Shariah compliant investing
    "IslamicFinanceUSA", "MuslimCorner", "MuslimInvestors", "HalalInvestor",
    "InvestingForBeginners",
]

# Ticker pattern: 1-5 uppercase letters, optionally preceded by $ sign
TICKER_RE = re.compile(r'\b\$?([A-Z]{1,5})\b')

# Common false-positives to exclude
EXCLUDE_WORDS = {
    "I", "A", "AN", "THE", "FOR", "AND", "BUT", "OR", "NOT", "IS", "IT",
    "TO", "OF", "IN", "ON", "AT", "BY", "UP", "IF", "NO", "SO", "DO",
    "GO", "BE", "AS", "WE", "HE", "ME", "US", "MY", "HIS", "HER", "ITS",
    "CEO", "CFO", "IPO", "ETF", "USD", "EUR", "GDP", "CPI", "IMF",
    "SEC", "FDA", "DOJ", "FTC", "FED", "NYSE", "OTC", "DD", "YOLO",
    "EOD", "EOY", "ATH", "ATL", "IMO", "IIRC", "TBH", "FYI", "NGL",
    "EPS", "PE", "PB", "FCF", "DCF", "EV", "EBITDA", "YOY", "QOQ",
    "FOMC", "SPY", "QQQ", "IWM", "VIX", "MACD", "RSI", "EMA", "SMA",
    "AI", "ML", "AR", "VR", "US", "UK", "EU", "CA", "AU",
}

USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "argus-scraper/0.1 by makhskham")

_has_credentials = bool(
    os.environ.get("REDDIT_CLIENT_ID") and
    os.environ.get("REDDIT_CLIENT_SECRET") and
    os.environ.get("REDDIT_CLIENT_ID") != "PASTE_YOUR_REDDIT_CLIENT_ID_HERE"
)


def extract_tickers(text: str) -> list[str]:
    """Extract potential stock tickers from text."""
    matches = TICKER_RE.findall(text)
    return [m for m in matches if m not in EXCLUDE_WORDS and len(m) >= 2]


# ──────────────────────────────────────────────────────────
# PUBLIC JSON API (no credentials needed)
# ──────────────────────────────────────────────────────────

async def _fetch_json(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        r = await client.get(url, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("fetch failed %s: %s", url, e)
        return None


def _post_data_to_signal(post: dict, subreddit: str) -> RawSignal | None:
    try:
        d = post.get("data", {})
        body = d.get("selftext") or d.get("title") or ""
        if not body:
            return None
        return RawSignal(
            source=f"r/{subreddit}",
            source_type="reddit",
            external_id=d["id"],
            subreddit=subreddit,
            author=d.get("author", "[deleted]"),
            title=d.get("title"),
            body=body[:8000],
            url=f"https://reddit.com{d.get('permalink', '')}",
            upvotes=int(d.get("score", 0)),
            upvote_ratio=float(d.get("upvote_ratio", 0)),
            posted_at=datetime.fromtimestamp(
                float(d.get("created_utc", 0)), tz=timezone.utc
            ),
        )
    except Exception:
        return None


def _comment_data_to_signal(c: dict, subreddit: str, post_id: str) -> RawSignal | None:
    try:
        d = c.get("data", {})
        body = d.get("body", "")
        if not body or body in ("[deleted]", "[removed]") or len(body) < 40:
            return None
        comment_id = d.get("id", "")
        return RawSignal(
            source=f"r/{subreddit}",
            source_type="reddit",
            external_id=f"c_{comment_id}",
            subreddit=subreddit,
            author=d.get("author", "[deleted]"),
            body=body[:4000],
            url=f"https://reddit.com/r/{subreddit}/comments/{post_id}/_/{comment_id}",
            upvotes=int(d.get("score", 0)),
            upvote_ratio=0.0,
            posted_at=datetime.fromtimestamp(
                float(d.get("created_utc", 0)), tz=timezone.utc
            ),
        )
    except Exception:
        return None


def _extract_comments(listing: list, subreddit: str, post_id: str) -> list[RawSignal]:
    signals = []
    for item in listing:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        if kind == "t1":
            sig = _comment_data_to_signal(item, subreddit, post_id)
            if sig:
                signals.append(sig)
            # Recurse into replies
            replies = item.get("data", {}).get("replies", {})
            if isinstance(replies, dict):
                children = replies.get("data", {}).get("children", [])
                signals.extend(_extract_comments(children, subreddit, post_id))
        elif kind == "Listing":
            children = item.get("data", {}).get("children", [])
            signals.extend(_extract_comments(children, subreddit, post_id))
    return signals


async def scrape_subreddit_public(subreddit_name: str, limit: int = 50) -> list[RawSignal]:
    """Scrape using Reddit's public JSON API. No credentials needed."""
    signals: list[RawSignal] = []

    async with httpx.AsyncClient(timeout=30) as client:
        # Fetch hot posts
        # old.reddit.com is less aggressive with blocking than www.reddit.com
        url = f"https://old.reddit.com/r/{subreddit_name}/hot.json?limit={limit}"
        data = await _fetch_json(client, url)
        if not data:
            return signals

        posts = data.get("data", {}).get("children", [])
        for post in posts:
            sig = _post_data_to_signal(post, subreddit_name)
            if sig:
                signals.append(sig)

            # Fetch comments for each post
            post_id = post.get("data", {}).get("id")
            if post_id:
                comment_url = (
                    f"https://old.reddit.com/r/{subreddit_name}"
                    f"/comments/{post_id}.json?limit=50&depth=3"
                )
                cdata = await _fetch_json(client, comment_url)
                if cdata and isinstance(cdata, list) and len(cdata) > 1:
                    comment_listing = cdata[1].get("data", {}).get("children", [])
                    signals.extend(
                        _extract_comments(comment_listing, subreddit_name, post_id)
                    )

            await asyncio.sleep(0.5)

    log.info("r/%s (public): scraped %d signals", subreddit_name, len(signals))
    return signals


# ──────────────────────────────────────────────────────────
# PRAW API (requires credentials - more reliable)
# ──────────────────────────────────────────────────────────

async def scrape_subreddit_praw(subreddit_name: str, limit: int = 100) -> list[RawSignal]:
    """Scrape using PRAW with Reddit API credentials."""
    import praw
    from .config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET

    loop = asyncio.get_event_loop()

    def _fetch() -> list[RawSignal]:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=USER_AGENT,
        )
        sub = reddit.subreddit(subreddit_name)
        results: list[RawSignal] = []
        for post in sub.hot(limit=limit):
            body = post.selftext or post.title
            results.append(RawSignal(
                source=f"r/{subreddit_name}",
                source_type="reddit",
                external_id=post.id,
                subreddit=subreddit_name,
                author=str(post.author) if post.author else "[deleted]",
                title=post.title,
                body=body[:8000],
                url=f"https://reddit.com{post.permalink}",
                upvotes=post.score,
                upvote_ratio=post.upvote_ratio,
                posted_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
            ))
            post.comments.replace_more(limit=5)
            for comment in post.comments.list():
                if not comment.body or comment.body in ("[deleted]", "[removed]"):
                    continue
                if len(comment.body) < 40:
                    continue
                results.append(RawSignal(
                    source=f"r/{subreddit_name}",
                    source_type="reddit",
                    external_id=f"c_{comment.id}",
                    subreddit=subreddit_name,
                    author=str(comment.author) if comment.author else "[deleted]",
                    body=comment.body[:4000],
                    url=f"https://reddit.com/r/{subreddit_name}/comments/{post.id}/_/{comment.id}",
                    upvotes=comment.score,
                    upvote_ratio=0.0,
                    posted_at=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
                ))
        return results

    try:
        signals = await loop.run_in_executor(None, _fetch)
        log.info("r/%s (PRAW): scraped %d signals", subreddit_name, len(signals))
        return signals
    except Exception as e:
        log.error("r/%s PRAW failed, trying public API: %s", subreddit_name, e)
        return await scrape_subreddit_public(subreddit_name, limit=50)


# ──────────────────────────────────────────────────────────
# Unified entry points
# ──────────────────────────────────────────────────────────

async def scrape_subreddit(subreddit_name: str, limit: int = 100) -> list[RawSignal]:
    """Auto-selects PRAW if credentials available, else public JSON API."""
    if _has_credentials:
        return await scrape_subreddit_praw(subreddit_name, limit)
    else:
        log.info("No Reddit credentials - using public JSON API for r/%s", subreddit_name)
        return await scrape_subreddit_public(subreddit_name, limit=min(limit, 50))


async def scrape_all_subreddits() -> list[RawSignal]:
    """Scrape all subreddits concurrently."""
    mode = "PRAW" if _has_credentials else "public JSON (no credentials)"
    log.info("Scraping %d subreddits via %s", len(SUBREDDITS), mode)

    # Run subreddits in batches to avoid overwhelming rate limits
    batch_size = 5 if _has_credentials else 3
    all_signals: list[RawSignal] = []

    for i in range(0, len(SUBREDDITS), batch_size):
        batch = SUBREDDITS[i:i + batch_size]
        tasks = [scrape_subreddit(sub) for sub in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_signals.extend(r)
        if i + batch_size < len(SUBREDDITS):
            await asyncio.sleep(2)  # pause between batches

    log.info("Total signals scraped: %d", len(all_signals))
    return all_signals
