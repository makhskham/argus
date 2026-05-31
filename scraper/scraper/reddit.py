import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import praw
from praw.models import Submission, Comment

from .config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from .models import RawSignal

log = logging.getLogger(__name__)

# All investment subreddits — large caps + small cap / niche communities
SUBREDDITS = [
    # Large/mainstream
    "investing", "stocks", "StockMarket", "Bogleheads", "dividends",
    "ValueInvesting", "SecurityAnalysis", "wallstreetbets", "Options",
    "Daytrading", "CanadianInvestor", "algotrading", "thetagang",
    # Small cap / niche / emerging — critical for hidden gem detection
    "pennystocks", "Superstonk", "smallcap", "RobinhoodPennyStocks",
    "undervalued", "MicroCapStocks", "OTCstocks", "investing_discussion",
    "weedstocks", "EVstocks", "stocks_advice", "stockmarketnews",
]

# Ticker pattern: 1-5 uppercase letters, optionally preceded by $ sign
TICKER_RE = re.compile(r'\b\$?([A-Z]{1,5})\b')

# Common false-positives to exclude (words that look like tickers)
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


def extract_tickers(text: str) -> list[str]:
    """Extract potential stock tickers from text."""
    matches = TICKER_RE.findall(text)
    return [m for m in matches if m not in EXCLUDE_WORDS and len(m) >= 2]


def _reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )


def _post_to_signal(post: Submission, subreddit: str) -> RawSignal:
    body = post.selftext or post.title
    return RawSignal(
        source=f"r/{subreddit}",
        source_type="reddit",
        external_id=post.id,
        subreddit=subreddit,
        author=str(post.author) if post.author else "[deleted]",
        title=post.title,
        body=body[:8000],
        url=f"https://reddit.com{post.permalink}",
        upvotes=post.score,
        upvote_ratio=post.upvote_ratio,
        posted_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
    )


def _comment_to_signal(
    comment: Comment, subreddit: str, post_id: str
) -> Optional[RawSignal]:
    if not comment.body or comment.body in ("[deleted]", "[removed]"):
        return None
    if len(comment.body) < 40:
        return None
    return RawSignal(
        source=f"r/{subreddit}",
        source_type="reddit",
        external_id=f"c_{comment.id}",
        subreddit=subreddit,
        author=str(comment.author) if comment.author else "[deleted]",
        body=comment.body[:4000],
        url=f"https://reddit.com/r/{subreddit}/comments/{post_id}/_/{comment.id}",
        upvotes=comment.score,
        upvote_ratio=0.0,
        posted_at=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
    )


async def scrape_subreddit(subreddit_name: str, limit: int = 100) -> list[RawSignal]:
    """Scrape hot posts + all comments from a subreddit."""
    loop = asyncio.get_event_loop()

    def _fetch() -> list[RawSignal]:
        reddit = _reddit_client()
        sub = reddit.subreddit(subreddit_name)
        results: list[RawSignal] = []
        for post in sub.hot(limit=limit):
            results.append(_post_to_signal(post, subreddit_name))
            post.comments.replace_more(limit=5)
            for comment in post.comments.list():
                sig = _comment_to_signal(comment, subreddit_name, post.id)
                if sig:
                    results.append(sig)
        return results

    try:
        signals = await loop.run_in_executor(None, _fetch)
        log.info("r/%s: scraped %d signals", subreddit_name, len(signals))
        return signals
    except Exception as e:
        log.error("r/%s scrape failed: %s", subreddit_name, e)
        return []


async def scrape_all_subreddits() -> list[RawSignal]:
    """Scrape all subreddits concurrently."""
    # Stagger slightly to avoid hitting Reddit rate limits simultaneously
    tasks = [scrape_subreddit(sub) for sub in SUBREDDITS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    signals: list[RawSignal] = []
    for r in results:
        if isinstance(r, list):
            signals.extend(r)
    return signals
