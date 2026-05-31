import asyncio
import logging

import asyncpg
from dotenv import load_dotenv

from .config import DATABASE_URL
from .reddit import scrape_all_subreddits
from .models import RawSignal
from .velocity import calculate_velocity, detect_emerging_tickers

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def save_signals(conn: asyncpg.Connection, signals: list[RawSignal]) -> int:
    saved = 0
    for sig in signals:
        try:
            await conn.execute(
                """
                INSERT INTO signals
                  (source, source_type, external_id, subreddit, author, title, body, url, upvotes, upvote_ratio, posted_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (source_type, external_id) DO NOTHING
                """,
                sig.source, sig.source_type, sig.external_id, sig.subreddit,
                sig.author, sig.title, sig.body, sig.url,
                sig.upvotes, sig.upvote_ratio, sig.posted_at,
            )
            saved += 1
        except Exception as e:
            log.warning("insert failed: %s", e)
    return saved


async def run_cycle() -> None:
    db_url = DATABASE_URL.replace("+asyncpg", "")
    pool = await asyncpg.create_pool(db_url)

    async with pool.acquire() as conn:
        cycle_id = await conn.fetchval(
            "INSERT INTO scrape_cycles DEFAULT VALUES RETURNING id"
        )
        log.info("scrape cycle %d started", cycle_id)

        # 1. Scrape all sources
        signals = await scrape_all_subreddits()
        saved = await save_signals(conn, signals)
        log.info("cycle %d: %d signals saved", cycle_id, saved)

        # 2. Calculate mention velocity for emerging ticker detection
        try:
            await calculate_velocity(conn)
            await detect_emerging_tickers(conn)
        except Exception as e:
            log.warning("velocity/emerging detection failed: %s", e)

        # 3. Mark cycle complete
        await conn.execute(
            "UPDATE scrape_cycles SET status='complete', finished_at=NOW(), signals_added=$2 WHERE id=$1",
            cycle_id, saved,
        )
        log.info("cycle %d complete", cycle_id)

    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_cycle())
