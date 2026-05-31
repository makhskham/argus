"""
Twitter/X scraper using Twikit.

Twikit (https://github.com/d60/twikit) allows searching Twitter/X without
an official API key by using the same internal GraphQL API the web app uses.
This is for personal private use only.

Setup (one-time):
  pip install twikit
  Then set TWITTER_USERNAME, TWITTER_EMAIL, TWITTER_PASSWORD in .env
  On first run, Twikit saves a cookies file so you don't need to log in again.

Financial Twitter (fintwit) is extremely high signal for:
- Breaking news before mainstream press picks it up
- Real-time sentiment from professional traders and analysts
- Ticker cashtags ($NVDA, $AAPL) with directional commentary
- Early signals from domain experts in niche industries

If credentials are not set, this module logs a warning and returns empty list.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from .models import RawSignal

log = logging.getLogger(__name__)

TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME", "")
TWITTER_EMAIL = os.environ.get("TWITTER_EMAIL", "")
TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD", "")
COOKIES_FILE = Path(__file__).parent / "twitter_cookies.json"

_has_credentials = bool(TWITTER_USERNAME and TWITTER_EMAIL and TWITTER_PASSWORD)

# Fintwit search queries — financial Twitter cashtag searches
FINTWIT_QUERIES = [
    "($NVDA OR $MSFT OR $PLTR) min_faves:50",
    "small cap hidden gem $stock min_faves:20",
    "under the radar stock min_faves:30",
    "micro cap catalyst min_faves:20",
    "short squeeze float min_faves:50",
    "FDA approval catalyst min_faves:30",
]


def _tweet_to_signal(tweet: object) -> RawSignal | None:
    try:
        # Twikit tweet object attributes
        text = getattr(tweet, "text", "") or ""
        if not text or len(text) < 20:
            return None

        tweet_id = str(getattr(tweet, "id", ""))
        user = getattr(tweet, "user", None)
        username = getattr(user, "screen_name", "unknown") if user else "unknown"
        created_at = getattr(tweet, "created_at", None)

        posted_at = datetime.now(tz=timezone.utc)
        if created_at:
            try:
                posted_at = datetime.strptime(
                    created_at, "%a %b %d %H:%M:%S %z %Y"
                )
            except Exception:
                pass

        favorite_count = getattr(tweet, "favorite_count", 0) or 0
        retweet_count = getattr(tweet, "retweet_count", 0) or 0

        return RawSignal(
            source="Twitter/X",
            source_type="other",
            external_id=f"tw_{tweet_id}",
            subreddit=None,
            author=username,
            title=None,
            body=text[:1000],
            url=f"https://twitter.com/{username}/status/{tweet_id}",
            upvotes=int(favorite_count) + int(retweet_count),
            upvote_ratio=0.0,
            posted_at=posted_at,
        )
    except Exception as e:
        log.debug("tweet parse error: %s", e)
        return None


async def _login_twikit():
    """Initialize and return an authenticated Twikit client."""
    try:
        from twikit import Client as TwikitClient  # type: ignore
    except ImportError:
        log.warning("twikit not installed. Run: pip install twikit")
        return None

    client = TwikitClient("en-US")

    if COOKIES_FILE.exists():
        try:
            client.load_cookies(str(COOKIES_FILE))
            log.info("twitter: loaded cookies from %s", COOKIES_FILE)
            return client
        except Exception:
            log.info("twitter: cookies invalid, re-logging in")

    try:
        await client.login(
            auth_info_1=TWITTER_USERNAME,
            auth_info_2=TWITTER_EMAIL,
            password=TWITTER_PASSWORD,
        )
        client.save_cookies(str(COOKIES_FILE))
        log.info("twitter: logged in as @%s, cookies saved", TWITTER_USERNAME)
        return client
    except Exception as e:
        log.error("twitter login failed: %s", e)
        return None


async def search_fintwit(query: str, limit: int = 20) -> list[RawSignal]:
    """Search Twitter/X for a specific query."""
    if not _has_credentials:
        return []

    client = await _login_twikit()
    if not client:
        return []

    signals: list[RawSignal] = []
    try:
        tweets = await client.search_tweet(query, product="Latest", count=limit)
        for tweet in tweets:
            sig = _tweet_to_signal(tweet)
            if sig:
                signals.append(sig)
        log.info("twitter '%s': %d signals", query[:40], len(signals))
    except Exception as e:
        log.warning("twitter search failed '%s': %s", query[:40], e)

    return signals


async def scrape_all_fintwit() -> list[RawSignal]:
    """Run all fintwit queries and return combined signals."""
    if not _has_credentials:
        log.info("twitter: no credentials set - skipping (optional)")
        return []

    all_signals: list[RawSignal] = []
    for query in FINTWIT_QUERIES:
        sigs = await search_fintwit(query, limit=20)
        all_signals.extend(sigs)
        await asyncio.sleep(2)  # respect rate limits between searches

    log.info("twitter total: %d signals", len(all_signals))
    return all_signals


async def search_ticker_twitter(ticker: str, limit: int = 30) -> list[RawSignal]:
    """Search Twitter for mentions of a specific ticker."""
    query = f"${ticker} -is:retweet lang:en"
    return await search_fintwit(query, limit=limit)
