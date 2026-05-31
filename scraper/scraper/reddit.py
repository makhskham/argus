import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import praw
from praw.models import Submission, Comment

from .config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from .models import RawSignal

log = logging.getLogger(__name__)

SUBREDDITS = [
    "investing", "stocks", "StockMarket", "Bogleheads", "dividends",
    "ValueInvesting", "SecurityAnalysis", "wallstreetbets", "Options",
    "Daytrading", "CanadianInvestor", "algotrading", "pennystocks",
    "Superstonk", "thetagang",
]


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


def _comment_to_signal(comment: Comment, subreddit: str, post_id: str) -> Optional[RawSignal]:
    if not comment.body or comment.body in ("[deleted]", "[removed]"):
        return None
    if len(comment.body) < 50:
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
    loop = asyncio.get_event_loop()
    signals: list[RawSignal] = []

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
    except Exception as e:
        log.error("r/%s scrape failed: %s", subreddit_name, e)

    return signals


async def scrape_all_subreddits() -> list[RawSignal]:
    tasks = [scrape_subreddit(sub) for sub in SUBREDDITS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    signals: list[RawSignal] = []
    for r in results:
        if isinstance(r, list):
            signals.extend(r)
    return signals
