"""
Argus scrape worker.

Full pipeline - all sources require zero credentials:

1.  Reddit RSS feeds       - Official Reddit feeds, real-time new posts, no auth
2.  Reddit JSON API        - Hot posts + all comments, 25 subreddits, no auth
3.  Arctic Shift           - Search ALL of Reddit history by keyword, no auth
4.  PullPush               - Pushshift continuation, historical depth back to 2005
5.  Stocktwits             - Real-time retail investor cashtag sentiment
6.  Seeking Alpha          - Analyst articles and buy/sell theses
7.  Twitter/X (optional)  - Fintwit signals via Twikit (needs burner account)
8.  Velocity + emerging    - Momentum scoring and hidden gem detection
"""
import asyncio
import logging

import asyncpg
from dotenv import load_dotenv

from .config import DATABASE_URL
from .rss import scrape_all_rss
from .reddit import scrape_all_subreddits
from .arctic_shift import search_investment_signals
from .pullpush import search_niche_discovery
from .stocktwits import scrape_all_stocktwits
from .seeking_alpha import scrape_latest_articles
from .twitter import scrape_all_fintwit
from .models import RawSignal
from .velocity import calculate_velocity, detect_emerging_tickers
from .analyzer import run_analysis
from .recommender import build_recommendations

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def save_signals(conn: asyncpg.Connection, signals: list[RawSignal]) -> int:
    saved = 0
    for sig in signals:
        try:
            await conn.execute(
                """
                INSERT INTO signals
                  (source, source_type, external_id, subreddit, author,
                   title, body, url, upvotes, upvote_ratio, posted_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (source_type, external_id) DO NOTHING
                """,
                sig.source, sig.source_type, sig.external_id,
                sig.subreddit, sig.author, sig.title, sig.body,
                sig.url, sig.upvotes, sig.upvote_ratio, sig.posted_at,
            )
            saved += 1
        except Exception as e:
            log.debug("insert skip: %s", e)
    return saved


async def run_cycle() -> None:
    db_url = DATABASE_URL.replace("+asyncpg", "")
    pool = await asyncpg.create_pool(db_url)

    async with pool.acquire() as conn:
        cycle_id = await conn.fetchval(
            "INSERT INTO scrape_cycles DEFAULT VALUES RETURNING id"
        )
        log.info("=" * 60)
        log.info("ARGUS SCRAPE CYCLE %d STARTED", cycle_id)
        log.info("=" * 60)

        total_saved = 0

        # 1. Reddit RSS (official Reddit feeds - real-time new posts, no auth)
        log.info("[1/7] Reddit RSS feeds (real-time new posts)...")
        try:
            rss_signals = await scrape_all_rss()
            saved = await save_signals(conn, rss_signals)
            total_saved += saved
            log.info("  RSS: %d signals saved", saved)
        except Exception as e:
            log.warning("  RSS failed (non-critical): %s", e)

        # 2. Reddit JSON API (hot posts + all comments, no auth)
        log.info("[2/7] Reddit JSON API (hot posts + comments)...")
        try:
            reddit_signals = await scrape_all_subreddits()
            saved = await save_signals(conn, reddit_signals)
            total_saved += saved
            log.info("  JSON API: %d signals saved", saved)
        except Exception as e:
            log.error("  Reddit JSON failed: %s", e)

        # 3. Arctic Shift (search ALL of Reddit history, no auth)
        log.info("[3/7] Arctic Shift (all-Reddit keyword search)...")
        try:
            arctic_signals = await search_investment_signals(days_back=30)
            saved = await save_signals(conn, arctic_signals)
            total_saved += saved
            log.info("  Arctic Shift: %d signals saved", saved)
        except Exception as e:
            log.warning("  Arctic Shift failed (non-critical): %s", e)

        # 4. PullPush (Pushshift continuation, history back to 2005)
        log.info("[4/7] PullPush (historical Reddit archive)...")
        try:
            pullpush_signals = await search_niche_discovery(days_back=3)
            saved = await save_signals(conn, pullpush_signals)
            total_saved += saved
            log.info("  PullPush: %d signals saved", saved)
        except Exception as e:
            log.warning("  PullPush failed (non-critical): %s", e)

        # 5. Stocktwits (real-time retail cashtag sentiment)
        log.info("[5/7] Stocktwits...")
        try:
            st_signals = await scrape_all_stocktwits()
            saved = await save_signals(conn, st_signals)
            total_saved += saved
            log.info("  Stocktwits: %d signals saved", saved)
        except Exception as e:
            log.warning("  Stocktwits failed (non-critical): %s", e)

        # 6. Seeking Alpha (analyst articles)
        log.info("[6/7] Seeking Alpha...")
        try:
            sa_signals = await scrape_latest_articles(limit=20)
            saved = await save_signals(conn, sa_signals)
            total_saved += saved
            log.info("  Seeking Alpha: %d signals saved", saved)
        except Exception as e:
            log.warning("  Seeking Alpha failed (non-critical): %s", e)

        # 7. Twitter/X fintwit (optional - needs burner account + twikit)
        log.info("[7/7] Twitter/X fintwit (optional)...")
        try:
            twitter_signals = await scrape_all_fintwit()
            if twitter_signals:
                saved = await save_signals(conn, twitter_signals)
                total_saved += saved
                log.info("  Twitter: %d signals saved", saved)
            else:
                log.info("  Twitter: skipped (set TWITTER_* env vars to enable)")
        except Exception as e:
            log.warning("  Twitter failed (non-critical): %s", e)

        # Velocity scoring + emerging ticker detection
        log.info("Running velocity scoring and emerging ticker detection...")
        try:
            await calculate_velocity(conn)
            await detect_emerging_tickers(conn)
        except Exception as e:
            log.warning("  Velocity detection failed (non-critical): %s", e)

        # Claude signal analysis (extract tickers, sentiment, confidence)
        log.info("Running Claude signal analysis...")
        try:
            analyzed = await run_analysis(conn, hours_back=48, max_signals=300)
            log.info("  Analysis: %d signals processed", analyzed)
        except Exception as e:
            log.warning("  Analysis failed (non-critical): %s", e)

        # Build ranked recommendations from analyzed signals
        log.info("Building recommendations...")
        try:
            recs = await build_recommendations(conn, cycle_id)
            log.info("  Recommendations: %d entries built", recs)
        except Exception as e:
            log.warning("  Recommendations failed (non-critical): %s", e)

        # Mark cycle complete
        await conn.execute(
            """UPDATE scrape_cycles
               SET status='complete', finished_at=NOW(), signals_added=$2
               WHERE id=$1""",
            cycle_id, total_saved,
        )

        log.info("=" * 60)
        log.info("CYCLE %d COMPLETE - %d signals saved", cycle_id, total_saved)
        log.info("=" * 60)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_cycle())
