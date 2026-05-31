"""
Twitter/X scraper using Twikit.

Twikit (https://github.com/d60/twikit) uses Twitter's internal GraphQL API -
the same one the web app uses - so no official API key is needed.
Personal private use only.

Two scraping modes:
1. Home timeline - tweets from accounts you follow on @m_argus_k
   These are curated by you (tech, stocks, crypto, news, politics) so
   every tweet is already from a trusted/relevant source.
2. Keyword search - broader fintwit cashtag searches across all of Twitter

The followed accounts timeline is the higher-signal source because
you've personally curated who to follow.
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

# Keyword searches across all of Twitter (broader discovery)
FINTWIT_QUERIES = [
    "($NVDA OR $MSFT OR $PLTR) min_faves:50",
    "small cap hidden gem $stock min_faves:20",
    "under the radar stock min_faves:30",
    "micro cap catalyst min_faves:20",
    "short squeeze float min_faves:50",
    "FDA approval catalyst min_faves:30",
    "breaking news market moving min_faves:100",
    "deal acquisition merger stock min_faves:50",
]

# Cached client across the scrape cycle to avoid repeated logins
_client_cache = None


def _tweet_to_signal(tweet: object, source_label: str = "Twitter/X") -> RawSignal | None:
    try:
        text = getattr(tweet, "text", "") or ""
        if not text or len(text) < 20:
            return None

        # Skip pure retweets - we want original thoughts
        if text.startswith("RT @"):
            return None

        tweet_id = str(getattr(tweet, "id", ""))
        user = getattr(tweet, "user", None)
        username = getattr(user, "screen_name", "unknown") if user else "unknown"
        display_name = getattr(user, "name", username) if user else username
        followers = getattr(user, "followers_count", 0) if user else 0
        created_at = getattr(tweet, "created_at", None)

        posted_at = datetime.now(tz=timezone.utc)
        if created_at:
            try:
                posted_at = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            except Exception:
                try:
                    # Some versions return ISO format
                    posted_at = datetime.fromisoformat(
                        created_at.replace("Z", "+00:00")
                    )
                except Exception:
                    pass

        favorite_count = int(getattr(tweet, "favorite_count", 0) or 0)
        retweet_count = int(getattr(tweet, "retweet_count", 0) or 0)
        reply_count = int(getattr(tweet, "reply_count", 0) or 0)

        # Weighted engagement score: likes + 2x RTs (RTs spread signal further)
        engagement = favorite_count + (retweet_count * 2) + reply_count

        # Enrich body with account context if it's a high-follower account
        body = text
        if followers > 10_000:
            body = f"[{display_name} | {followers:,} followers] {text}"

        return RawSignal(
            source=source_label,
            source_type="other",
            external_id=f"tw_{tweet_id}",
            subreddit=None,
            author=username,
            title=None,
            body=body[:1000],
            url=f"https://twitter.com/{username}/status/{tweet_id}",
            upvotes=engagement,
            upvote_ratio=0.0,
            posted_at=posted_at,
        )
    except Exception as e:
        log.debug("tweet parse error: %s", e)
        return None


async def _get_client():
    """Return an authenticated Twikit client, reusing across the scrape cycle."""
    global _client_cache
    if _client_cache is not None:
        return _client_cache

    try:
        from twikit import Client as TwikitClient  # type: ignore
    except ImportError:
        log.warning("twikit not installed - run: pip install twikit")
        return None

    client = TwikitClient("en-US")

    if COOKIES_FILE.exists():
        try:
            client.load_cookies(str(COOKIES_FILE))
            log.info("twitter: loaded session cookies")
            _client_cache = client
            return client
        except Exception:
            log.info("twitter: cookies expired, logging in fresh")

    try:
        # auth_info_1 = username, auth_info_2 = email (for 2-step verification)
        await client.login(
            auth_info_1=TWITTER_USERNAME,
            auth_info_2=TWITTER_EMAIL,
            password=TWITTER_PASSWORD,
        )
        client.save_cookies(str(COOKIES_FILE))
        log.info("twitter: logged in as @%s, cookies saved", TWITTER_USERNAME)
        _client_cache = client
        return client
    except Exception as e:
        log.warning("twitter login failed (%s) - run: pip install --upgrade twikit", e)
        return None


async def scrape_home_timeline(count: int = 100) -> list[RawSignal]:
    """
    Fetch the home timeline - tweets from accounts @m_argus_k follows.

    This is the highest-signal source because the followed accounts are
    personally curated: tech analysts, traders, market news, politics.
    Every tweet here is already from a source deemed worth watching.
    """
    if not _has_credentials:
        return []

    client = await _get_client()
    if not client:
        return []

    signals: list[RawSignal] = []
    try:
        # get_timeline() returns tweets from followed accounts
        tweets = await client.get_timeline(count=count)
        for tweet in tweets:
            sig = _tweet_to_signal(tweet, source_label="Twitter/Following")
            if sig:
                signals.append(sig)
        log.info("twitter timeline: %d signals from followed accounts", len(signals))
    except Exception as e:
        log.warning("twitter timeline failed: %s", e)

    return signals


async def scrape_latest_timeline(count: int = 50) -> list[RawSignal]:
    """
    Fetch 'For You' / latest tweets timeline - broader Twitter discovery.
    Complements the home timeline with algorithmically surfaced content.
    """
    if not _has_credentials:
        return []

    client = await _get_client()
    if not client:
        return []

    signals: list[RawSignal] = []
    try:
        tweets = await client.get_latest_timeline(count=count)
        for tweet in tweets:
            sig = _tweet_to_signal(tweet, source_label="Twitter/ForYou")
            if sig:
                signals.append(sig)
        log.info("twitter for-you: %d signals", len(signals))
    except Exception as e:
        log.warning("twitter for-you timeline failed: %s", e)

    return signals


async def search_fintwit(query: str, limit: int = 20) -> list[RawSignal]:
    """Search Twitter/X for a specific query across all accounts."""
    if not _has_credentials:
        return []

    client = await _get_client()
    if not client:
        return []

    signals: list[RawSignal] = []
    try:
        tweets = await client.search_tweet(query, product="Latest", count=limit)
        for tweet in tweets:
            sig = _tweet_to_signal(tweet, source_label="Twitter/Search")
            if sig:
                signals.append(sig)
    except Exception as e:
        log.warning("twitter search failed '%s': %s", query[:40], e)

    return signals


async def scrape_all_twitter() -> list[RawSignal]:
    """
    Full Twitter scrape:
    1. Home timeline (followed accounts - curated, high trust)
    2. For You timeline (algorithmic discovery)
    3. Keyword searches (broader fintwit discovery)
    """
    if not _has_credentials:
        log.info("twitter: no credentials - skipping")
        return []

    all_signals: list[RawSignal] = []

    # 1. Home timeline - followed accounts (highest priority)
    home = await scrape_home_timeline(count=100)
    all_signals.extend(home)
    await asyncio.sleep(2)

    # 2. For You timeline - algorithmic discovery
    foryou = await scrape_latest_timeline(count=50)
    all_signals.extend(foryou)
    await asyncio.sleep(2)

    # 3. Keyword searches across all Twitter
    for query in FINTWIT_QUERIES:
        sigs = await search_fintwit(query, limit=20)
        all_signals.extend(sigs)
        await asyncio.sleep(2)

    # Deduplicate by external_id
    seen = set()
    deduped = []
    for sig in all_signals:
        if sig.external_id not in seen:
            seen.add(sig.external_id)
            deduped.append(sig)

    log.info("twitter total: %d signals (%d from timeline, %d from search)",
             len(deduped), len(home) + len(foryou),
             len(deduped) - len(home) - len(foryou))
    return deduped


# Keep old name as alias so worker.py import still works
scrape_all_fintwit = scrape_all_twitter


async def search_ticker_twitter(ticker: str, limit: int = 30) -> list[RawSignal]:
    """Search Twitter for mentions of a specific ticker."""
    return await search_fintwit(
        f"${ticker} -is:retweet lang:en", limit=limit
    )
