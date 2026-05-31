"""
Seeking Alpha scraper using their public-facing endpoints.
"""
import logging
from datetime import datetime, timezone

import httpx

from .models import RawSignal

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://seekingalpha.com/",
    "Origin": "https://seekingalpha.com",
}


def _article_to_signal(article: dict) -> RawSignal | None:
    try:
        attrs = article.get("attributes", {})
        title = attrs.get("title", "")
        if not title:
            return None

        summary = attrs.get("summary", "") or attrs.get("paywall_summary", "") or ""
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

    # Try multiple endpoints since SA changes their API periodically
    endpoints = [
        "https://seekingalpha.com/api/v3/articles?filter[category]=market-outlook::stock-ideas&page[size]=20",
        "https://seekingalpha.com/api/v3/articles?filter[category]=stock-ideas&page[size]=20",
        "https://seekingalpha.com/api/v3/articles?page[size]=20&sort=-publishOn",
    ]

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in endpoints:
            try:
                r = await client.get(url, headers=HEADERS)
                if r.status_code == 200:
                    data = r.json()
                    for article in data.get("data", [])[:limit]:
                        sig = _article_to_signal(article)
                        if sig:
                            signals.append(sig)
                    if signals:
                        log.info("seeking alpha: %d articles via %s", len(signals), url)
                        return signals
            except Exception as e:
                log.debug("sa endpoint %s failed: %s", url, e)

    log.info("seeking alpha: 0 articles (all endpoints failed - SA may require login)")
    return signals


async def scrape_ticker_analysis(ticker: str) -> list[RawSignal]:
    """Get analyst articles for a specific ticker."""
    url = f"https://seekingalpha.com/api/v3/articles?filter[since]=30&filter[symbols]={ticker}&page[size]=10"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        try:
            r = await client.get(url, headers=HEADERS)
            if r.status_code != 200:
                return []
            data = r.json()
            signals = []
            for article in data.get("data", []):
                sig = _article_to_signal(article)
                if sig:
                    signals.append(sig)
            return signals
        except Exception:
            return []
