"""
Seeking Alpha article scraper.

Seeking Alpha publishes analyst articles with buy/sell recommendations
and community comments. The comment sections under popular articles
act as a mini-forum debating each stock's thesis.

Uses Playwright for JS-rendered pages and their internal API endpoints.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from .models import RawSignal

log = logging.getLogger(__name__)

# Seeking Alpha has internal API endpoints used by their own frontend
SA_API = "https://seekingalpha.com/api/v3"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://seekingalpha.com/",
}


async def _get(client: httpx.AsyncClient, url: str, params: dict = {}) -> dict | None:
    try:
        r = await client.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("seeking alpha %s: %s", url, e)
        return None


def _article_to_signal(article: dict) -> RawSignal | None:
    try:
        attrs = article.get("attributes", {})
        title = attrs.get("title", "")
        summary = attrs.get("summary", attrs.get("content", ""))
        if not title:
            return None

        body = f"{title}. {summary}".strip()[:6000]
        published = attrs.get("publishOn") or attrs.get("lastModified")
        posted_at = datetime.now(tz=timezone.utc)
        if published:
            try:
                posted_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            except Exception:
                pass

        article_id = str(article.get("id", ""))
        slug = attrs.get("slug", article_id)

        return RawSignal(
            source="SeekingAlpha",
            source_type="seeking_alpha",
            external_id=f"sa_{article_id}",
            subreddit=None,
            author=attrs.get("authorUserName", "analyst"),
            title=title,
            body=body,
            url=f"https://seekingalpha.com/article/{slug}",
            upvotes=int(attrs.get("commentCount", 0)),
            upvote_ratio=0.0,
            posted_at=posted_at,
        )
    except Exception as e:
        log.debug("sa article parse: %s", e)
        return None


async def scrape_latest_articles(limit: int = 20) -> list[RawSignal]:
    """Get latest analysis articles from Seeking Alpha."""
    signals: list[RawSignal] = []
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{SA_API}/articles", {
            "filter[category]": "market-outlook::stock-ideas",
            "include": "author,primaryTickers",
            "page[size]": limit,
            "page[number]": 1,
        })
        if not data:
            return signals
        for article in data.get("data", []):
            sig = _article_to_signal(article)
            if sig:
                signals.append(sig)
    log.info("seeking alpha: %d articles", len(signals))
    return signals


async def scrape_ticker_analysis(ticker: str) -> list[RawSignal]:
    """Get analyst articles for a specific ticker."""
    signals: list[RawSignal] = []
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{SA_API}/articles", {
            "filter[since]": "30",
            "filter[symbols]": ticker,
            "page[size]": 10,
        })
        if not data:
            return signals
        for article in data.get("data", []):
            sig = _article_to_signal(article)
            if sig:
                signals.append(sig)
    return signals
