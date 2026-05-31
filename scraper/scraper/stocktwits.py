"""
Stocktwits scraper using Playwright for JS-rendered content.
Falls back to their unofficial API endpoint if Playwright is unavailable.

Stocktwits is "Twitter for stocks" — real-time retail investor sentiment,
extremely high signal for short-term momentum and emerging ticker detection.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from .models import RawSignal

log = logging.getLogger(__name__)

# Unofficial Stocktwits API - publicly accessible, no auth needed
ST_API = "https://api.stocktwits.com/api/2"


async def _get(client: httpx.AsyncClient, url: str, params: dict = {}) -> dict | None:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        r = await client.get(url, params=params, headers=headers, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("stocktwits %s: %s", url, e)
        return None


def _message_to_signal(msg: dict, ticker: str | None = None) -> RawSignal | None:
    try:
        body = msg.get("body", "")
        if not body or len(body) < 20:
            return None

        created = msg.get("created_at")
        if created:
            posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
        else:
            posted_at = datetime.now(tz=timezone.utc)

        user = msg.get("user", {})
        msg_id = str(msg.get("id", ""))

        # Extract tickers from message symbols
        symbols = msg.get("symbols", [])
        source = ticker or (symbols[0]["symbol"] if symbols else "MARKET")

        return RawSignal(
            source=f"Stocktwits:{source}",
            source_type="stocktwits",
            external_id=f"st_{msg_id}",
            subreddit=None,
            author=user.get("username", "[unknown]"),
            title=None,
            body=body[:2000],
            url=f"https://stocktwits.com/{user.get('username', '')}/message/{msg_id}",
            upvotes=msg.get("likes", {}).get("total", 0),
            upvote_ratio=0.0,
            posted_at=posted_at,
        )
    except Exception as e:
        log.debug("stocktwits parse error: %s", e)
        return None


async def scrape_ticker_stream(ticker: str, limit: int = 30) -> list[RawSignal]:
    """Get recent messages for a specific ticker on Stocktwits."""
    signals: list[RawSignal] = []
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{ST_API}/streams/symbol/{ticker}.json", {
            "limit": min(limit, 30),
        })
        if not data:
            return signals
        for msg in data.get("messages", []):
            sig = _message_to_signal(msg, ticker)
            if sig:
                signals.append(sig)
    return signals


async def scrape_trending_stream() -> list[RawSignal]:
    """Get trending messages across all stocks on Stocktwits."""
    signals: list[RawSignal] = []
    async with httpx.AsyncClient() as client:
        data = await _get(client, f"{ST_API}/streams/trending.json", {"limit": 30})
        if not data:
            return signals
        for msg in data.get("messages", []):
            sig = _message_to_signal(msg)
            if sig:
                signals.append(sig)
    log.info("stocktwits trending: %d signals", len(signals))
    return signals


async def scrape_all_stocktwits(tickers: list[str] | None = None) -> list[RawSignal]:
    """Scrape trending + specific tickers from Stocktwits."""
    all_signals: list[RawSignal] = []

    # Always get trending
    trending = await scrape_trending_stream()
    all_signals.extend(trending)
    await asyncio.sleep(1)

    # Get ticker-specific streams if tickers provided
    if tickers:
        for ticker in tickers[:20]:  # cap at 20 to respect rate limits
            sigs = await scrape_ticker_stream(ticker)
            all_signals.extend(sigs)
            await asyncio.sleep(0.5)

    log.info("stocktwits total: %d signals", len(all_signals))
    return all_signals
