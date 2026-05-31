"""
Argus scrape worker.

Runs a full scrape cycle:
1. Reddit public JSON API (25 subreddits, no credentials needed)
2. Arctic Shift (ALL of Reddit historical search - hidden gem discovery)
3. PullPush (Pushshift continuation - deep historical search)
4. Stocktwits (real-time retail sentiment)
5. Seeking Alpha (analyst articles)
6. Mention velocity calculation + emerging ticker detection
"""
import asyncio
import logging

import asyncpg
from dotenv import load_dotenv

from .config import DATABASE_URL
from .reddit import scrape_all_subreddits
from .arctic_shift import search_investment_signals
from .pullpush import search_niche_discovery
from .twitter import scrape_all_fintwit
from .stocktwits import scrape_all_stocktwits
from .seeking_alpha import scrape_latest_articles
from .models import RawSignal
from .velocity import calculate_velocity, detect_emerging_tickers

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

        # 1. Reddit (25 subreddits via public JSON API)
        log.info("[1/4] Scraping Reddit subreddits...")
        try:
            reddit_signals = await scrape_all_subreddits()
            saved = await save_signals(conn, reddit_signals)
            total_saved += saved
            log.info("  Reddit: %d signals saved", saved)
        except Exception as e:
            log.error("  Reddit scrape failed: %s", e)

        # 2. Arctic Shift (hidden gem discovery across all of Reddit)
        log.info("[2/5] Scanning ALL of Reddit via Arctic Shift...")
        try:
            arctic_signals = await search_investment_signals(days_back=1)
            saved = await save_signals(conn, arctic_signals)
            total_saved += saved
            log.info("  Arctic Shift: %d signals saved", saved)
        except Exception as e:
            log.warning("  Arctic Shift failed (non-critical): %s", e)

        # 3. PullPush (Pushshift continuation - deep historical discovery)
        log.info("[3/5] Scanning Reddit history via PullPush...")
        try:
            pullpush_signals = await search_niche_discovery(days_back=3)
            saved = await save_signals(conn, pullpush_signals)
            total_saved += saved
            log.info("  PullPush: %d signals saved", saved)
        except Exception as e:
            log.warning("  PullPush failed (non-critical): %s", e)

        # 4. Stocktwits (real-time retail sentiment)
        log.info("[4/5] Scraping Stocktwits...")
        try:
            st_signals = await scrape_all_stocktwits()
            saved = await save_signals(conn, st_signals)
            total_saved += saved
            log.info("  Stocktwits: %d signals saved", saved)
        except Exception as e:
            log.warning("  Stocktwits failed (non-critical): %s", e)

        # 5. Twitter/X fintwit (optional - requires twikit + burner account)
        log.info("[5/6] Scraping Twitter/X fintwit...")
        try:
            twitter_signals = await scrape_all_fintwit()
            if twitter_signals:
                saved = await save_signals(conn, twitter_signals)
                total_saved += saved
                log.info("  Twitter: %d signals saved", saved)
            else:
                log.info("  Twitter: skipped (no credentials)")
        except Exception as e:
            log.warning("  Twitter failed (non-critical): %s", e)

        # 6. Seeking Alpha (analyst articles)
        log.info("[6/6] Scraping Seeking Alpha...")
        try:
            sa_signals = await scrape_latest_articles(limit=20)
            saved = await save_signals(conn, sa_signals)
            total_saved += saved
            log.info("  Seeking Alpha: %d signals saved", saved)
        except Exception as e:
            log.warning("  Seeking Alpha failed (non-critical): %s", e)

        # Velocity and emerging ticker detection
        log.info("Calculating mention velocity and detecting emerging tickers...")
        try:
            await calculate_velocity(conn)
            await detect_emerging_tickers(conn)
        except Exception as e:
            log.warning("  Velocity detection failed (non-critical): %s", e)

        # Mark cycle complete
        await conn.execute(
            """UPDATE scrape_cycles
               SET status='complete', finished_at=NOW(), signals_added=$2
               WHERE id=$1""",
            cycle_id, total_saved,
        )

        log.info("=" * 60)
        log.info("CYCLE %d COMPLETE - %d signals saved total", cycle_id, total_saved)
        log.info("=" * 60)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_cycle())
