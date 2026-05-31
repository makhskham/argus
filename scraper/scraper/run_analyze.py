"""
Standalone analysis runner.

Token-efficient design:
- Signals already analyzed are NEVER re-processed (deduplication by signal ID)
- Prioritizes freshest signals (last 3 days first, expands if budget allows)
- Deduplicates near-identical posts before sending to API
- Processes highest-upvote signals first (maximum signal quality per token)

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
        # Check how many signals are already analyzed (skip those entirely)
        already_done = await conn.fetchval("SELECT COUNT(*) FROM signal_analyses")
        total = await conn.fetchval("SELECT COUNT(*) FROM signals")
        remaining = total - already_done
        log.info(
            "Signal status: %d total, %d already analyzed, %d unprocessed",
            total, already_done, remaining
        )

        # Get or create a cycle for recommendations
        cycle_id = await conn.fetchval(
            """SELECT id FROM scrape_cycles
               WHERE status='complete'
               ORDER BY id DESC LIMIT 1"""
        )
        if not cycle_id:
            cycle_id = await conn.fetchval(
                "INSERT INTO scrape_cycles (status) VALUES ('complete') RETURNING id"
            )
        log.info("Using cycle_id=%d for recommendations", cycle_id)

        if remaining == 0:
            log.info("All signals already analyzed. Rebuilding recommendations only.")
        else:
            log.info("Step 1/2: Analyzing %d unprocessed signals (priority: freshest first)...", remaining)
            # Priority: last 3 days → 7 days → 14 days, max 300 per run to save tokens
            analyzed = await run_analysis(conn, hours_back=336, max_signals=300)
            log.info("Analysis complete: %d new analyses added", analyzed)

        log.info("Step 2/2: Building recommendations from all analyzed signals...")
        recs = await build_recommendations(conn, cycle_id, hours_back=336)
        log.info("Recommendations built: %d ranked entries", recs)

    await pool.close()
    log.info("Done. Refresh http://localhost:3000/dashboard")


if __name__ == "__main__":
    asyncio.run(main())
