"""
Standalone analysis runner.

Runs Claude analysis + recommendation building on signals already in DB.
Use this to populate the dashboard without re-scraping everything.

Usage:
  py -3 -m scraper.run_analyze
"""
import asyncio
import logging

import asyncpg
from dotenv import load_dotenv

from .config import DATABASE_URL
from .analyzer import run_analysis
from .recommender import build_recommendations

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def main() -> None:
    db_url = DATABASE_URL.replace("+asyncpg", "")
    pool = await asyncpg.create_pool(db_url)

    async with pool.acquire() as conn:
        # Create a scrape cycle entry for these recommendations
        cycle_id = await conn.fetchval(
            "INSERT INTO scrape_cycles (status) VALUES ('complete') RETURNING id"
        )
        log.info("Using cycle_id=%d for recommendations", cycle_id)

        log.info("Step 1/2: Running Claude signal analysis on existing signals...")
        analyzed = await run_analysis(conn, hours_back=72, max_signals=500)
        log.info("Analysis complete: %d signals processed", analyzed)

        log.info("Step 2/2: Building recommendations...")
        recs = await build_recommendations(conn, cycle_id, hours_back=168)
        log.info("Recommendations built: %d entries", recs)

        # Mark cycle as complete
        await conn.execute(
            "UPDATE scrape_cycles SET finished_at=NOW(), signals_added=$2 WHERE id=$1",
            cycle_id, analyzed,
        )

    await pool.close()
    log.info("Done. Refresh your dashboard at http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(main())
