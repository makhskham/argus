"""
Mention velocity tracker.

After each scrape cycle, calculates how fast each ticker's mention count
is growing. High velocity on a previously-obscure ticker = potential hidden gem.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import asyncpg

log = logging.getLogger(__name__)


async def calculate_velocity(conn: asyncpg.Connection) -> None:
    """
    Calculate mention velocity for all tickers seen in the last 48h.
    Velocity = mentions_last_6h / mentions_prev_6h (ratio, capped at 10x)
    A ticker mentioned 1x 12h ago and 20x in the last 6h has velocity=20.
    """
    now = datetime.now(tz=timezone.utc)
    window_recent = now - timedelta(hours=6)
    window_prev = now - timedelta(hours=12)

    # Count recent and previous window mentions per ticker
    rows = await conn.fetch("""
        WITH ticker_mentions AS (
            SELECT
                unnest(sa.tickers) AS ticker,
                s.posted_at,
                s.upvotes,
                s.source
            FROM signal_analyses sa
            JOIN signals s ON s.id = sa.signal_id
            WHERE s.posted_at >= $1
        ),
        recent AS (
            SELECT ticker,
                   COUNT(*) AS mention_count,
                   COUNT(DISTINCT source) AS unique_sources,
                   AVG(upvotes) AS avg_upvotes
            FROM ticker_mentions
            WHERE posted_at >= $2
            GROUP BY ticker
        ),
        prev AS (
            SELECT ticker, COUNT(*) AS mention_count
            FROM ticker_mentions
            WHERE posted_at >= $1 AND posted_at < $2
            GROUP BY ticker
        )
        SELECT
            r.ticker,
            r.mention_count AS recent_count,
            COALESCE(p.mention_count, 0) AS prev_count,
            r.unique_sources,
            r.avg_upvotes,
            CASE
                WHEN COALESCE(p.mention_count, 0) = 0 THEN r.mention_count::float
                ELSE r.mention_count::float / p.mention_count::float
            END AS velocity_ratio
        FROM recent r
        LEFT JOIN prev p ON p.ticker = r.ticker
        ORDER BY velocity_ratio DESC
    """, window_prev, window_recent)

    inserted = 0
    for row in rows:
        ticker = row["ticker"]
        velocity = min(float(row["velocity_ratio"]), 20.0)  # cap at 20x

        try:
            await conn.execute("""
                INSERT INTO ticker_velocity
                  (ticker, window_start, window_end, mention_count, unique_sources, avg_upvotes, velocity_score)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (ticker, window_start) DO UPDATE SET
                  mention_count = EXCLUDED.mention_count,
                  unique_sources = EXCLUDED.unique_sources,
                  avg_upvotes = EXCLUDED.avg_upvotes,
                  velocity_score = EXCLUDED.velocity_score
            """, ticker, window_recent, now,
                int(row["recent_count"]), int(row["unique_sources"]),
                float(row["avg_upvotes"]), velocity)
            inserted += 1
        except Exception as e:
            log.warning("velocity insert failed for %s: %s", ticker, e)

    log.info("velocity scores updated for %d tickers", inserted)


async def detect_emerging_tickers(conn: asyncpg.Connection) -> None:
    """
    Identify tickers that appear to be breaking out:
    - High velocity (>= 3x mention growth)
    - At least 2 unique sources
    - Average upvotes >= 10 (community interest)
    - Not already in recommendations as a well-known ticker
    Insert into emerging_tickers if not already there.
    """
    now = datetime.now(tz=timezone.utc)
    window = now - timedelta(hours=6)

    rows = await conn.fetch("""
        SELECT tv.ticker, tv.velocity_score, tv.unique_sources, tv.avg_upvotes,
               tv.mention_count,
               s.subreddit AS source_subreddit,
               s.body AS first_mention_body
        FROM ticker_velocity tv
        JOIN LATERAL (
            SELECT sa.tickers, s2.subreddit, s2.body
            FROM signal_analyses sa
            JOIN signals s2 ON s2.id = sa.signal_id
            WHERE tv.ticker = ANY(sa.tickers)
              AND s2.posted_at >= $1
            ORDER BY sa.confidence DESC
            LIMIT 1
        ) s ON true
        WHERE tv.window_start >= $1
          AND tv.velocity_score >= 3.0
          AND tv.unique_sources >= 2
          AND tv.avg_upvotes >= 5
          AND LENGTH(tv.ticker) BETWEEN 2 AND 5
        ORDER BY tv.velocity_score DESC
        LIMIT 50
    """, window)

    for row in rows:
        ticker = row["ticker"]
        graduation_score = (
            float(row["velocity_score"]) * 0.4 +
            float(row["unique_sources"]) * 10 +
            min(float(row["avg_upvotes"]) / 100, 1.0) * 20 +
            min(int(row["mention_count"]) / 10, 5.0) * 6
        )

        try:
            await conn.execute("""
                INSERT INTO emerging_tickers
                  (ticker, first_seen_at, initial_confidence, source_subreddit, first_mention_body, graduation_score)
                VALUES ($1, NOW(), $2, $3, $4, $5)
                ON CONFLICT (ticker) DO UPDATE SET
                  graduation_score = GREATEST(emerging_tickers.graduation_score, EXCLUDED.graduation_score)
            """, ticker, 50, row["source_subreddit"],
                (row["first_mention_body"] or "")[:500], graduation_score)
        except Exception as e:
            log.warning("emerging insert failed for %s: %s", ticker, e)

    log.info("emerging ticker detection complete, %d candidates evaluated", len(rows))
