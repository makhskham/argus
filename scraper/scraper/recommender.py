"""
Recommendation builder.

Reads signal_analyses from the database, aggregates by ticker,
calculates sentiment scores and confidence, and writes ranked
buy/avoid recommendations to the recommendations table.

This runs after each analysis batch to keep the dashboard current.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import asyncpg

log = logging.getLogger(__name__)

# Minimum number of signals needed to include a ticker in recommendations
MIN_SIGNALS = 2

# Minimum sources (subreddits/platforms) to avoid single-source noise
MIN_SOURCES = 1


async def build_recommendations(
    conn: asyncpg.Connection,
    cycle_id: int,
    hours_back: int = 168,  # 7 days
) -> int:
    """
    Aggregate signal_analyses by ticker and write recommendations.
    Returns number of tickers ranked.
    """
    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)

    # Aggregate sentiment by ticker
    rows = await conn.fetch("""
        SELECT
            sa.tickers,
            sa.sentiment,
            sa.confidence,
            sa.is_niche_flagged,
            s.source,
            s.subreddit,
            s.upvotes,
            ru.trust_tier
        FROM signal_analyses sa
        JOIN signals s ON s.id = sa.signal_id
        LEFT JOIN reddit_users ru ON ru.id = s.reddit_user_id
        WHERE s.posted_at >= $1
          AND array_length(sa.tickers, 1) > 0
    """, since)

    if not rows:
        log.info("recommender: no analyzed signals found in last %dh", hours_back)
        return 0

    # Build per-ticker aggregates
    # trust_weight: authority=2.0, trusted=1.5, recognized=1.2, else=1.0
    TRUST_WEIGHTS = {"authority": 2.0, "trusted": 1.5, "recognized": 1.2}

    ticker_data: dict[str, dict] = {}

    for row in rows:
        tickers = row["tickers"] or []
        weight = TRUST_WEIGHTS.get(row["trust_tier"] or "", 1.0)
        upvote_boost = min(1.0 + (row["upvotes"] or 0) / 10000, 2.0)
        effective_weight = weight * upvote_boost

        for ticker in tickers:
            if not ticker or len(ticker) > 5:
                continue
            if ticker not in ticker_data:
                ticker_data[ticker] = {
                    "bull": 0.0, "bear": 0.0, "neutral": 0.0,
                    "total_weight": 0.0, "sources": set(),
                    "confidence_sum": 0.0, "signal_count": 0,
                    "niche_count": 0,
                }
            td = ticker_data[ticker]
            sentiment = row["sentiment"] or "neutral"
            td[sentiment] += effective_weight
            td["total_weight"] += effective_weight
            td["sources"].add(row["source"] or "unknown")
            td["confidence_sum"] += (row["confidence"] or 50) * effective_weight
            td["signal_count"] += 1
            if row["is_niche_flagged"]:
                td["niche_count"] += 1

    if not ticker_data:
        log.info("recommender: no tickers extracted")
        return 0

    # Score each ticker
    scored = []
    for ticker, td in ticker_data.items():
        if td["signal_count"] < MIN_SIGNALS:
            continue
        if len(td["sources"]) < MIN_SOURCES:
            continue

        total = td["total_weight"] or 1.0
        bull_pct = (td["bull"] / total) * 100
        bear_pct = (td["bear"] / total) * 100
        neutral_pct = (td["neutral"] / total) * 100
        avg_confidence = td["confidence_sum"] / total

        # Direction: need at least 55% for a strong signal
        if bull_pct >= 55:
            direction = "buy"
            directional_score = bull_pct * (avg_confidence / 100)
        elif bear_pct >= 55:
            direction = "avoid"
            directional_score = bear_pct * (avg_confidence / 100)
        else:
            continue  # too mixed - skip

        # Momentum bonus for niche flags
        momentum_bonus = min(td["niche_count"] * 5, 20)
        final_score = directional_score + momentum_bonus

        scored.append({
            "ticker": ticker,
            "direction": direction,
            "confidence": min(100, int(avg_confidence)),
            "bull_pct": round(bull_pct, 1),
            "neutral_pct": round(neutral_pct, 1),
            "bear_pct": round(bear_pct, 1),
            "signal_count": td["signal_count"],
            "source_count": len(td["sources"]),
            "momentum_score": round(final_score, 2),
            "is_emerging": td["niche_count"] >= 2,
            "score": final_score,
        })

    # Sort: buy by score desc, avoid by score desc
    buy_list = sorted(
        [t for t in scored if t["direction"] == "buy"],
        key=lambda x: x["score"], reverse=True
    )[:30]

    avoid_list = sorted(
        [t for t in scored if t["direction"] == "avoid"],
        key=lambda x: x["score"], reverse=True
    )[:30]

    # Delete old recommendations for this cycle if any
    await conn.execute(
        "DELETE FROM recommendations WHERE cycle_id = $1", cycle_id
    )

    # Insert new recommendations
    total_inserted = 0
    for rank, rec in enumerate(buy_list, 1):
        try:
            await conn.execute("""
                INSERT INTO recommendations
                  (ticker, direction, rank, confidence, bull_pct, neutral_pct, bear_pct,
                   signal_count, source_count, momentum_score, is_emerging, cycle_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """, rec["ticker"], "buy", rank, rec["confidence"],
                rec["bull_pct"], rec["neutral_pct"], rec["bear_pct"],
                rec["signal_count"], rec["source_count"],
                rec["momentum_score"], rec["is_emerging"], cycle_id)
            total_inserted += 1
        except Exception as e:
            log.debug("insert buy rec %s: %s", rec["ticker"], e)

    for rank, rec in enumerate(avoid_list, 1):
        try:
            await conn.execute("""
                INSERT INTO recommendations
                  (ticker, direction, rank, confidence, bull_pct, neutral_pct, bear_pct,
                   signal_count, source_count, momentum_score, is_emerging, cycle_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """, rec["ticker"], "avoid", rank, rec["confidence"],
                rec["bull_pct"], rec["neutral_pct"], rec["bear_pct"],
                rec["signal_count"], rec["source_count"],
                rec["momentum_score"], rec["is_emerging"], cycle_id)
            total_inserted += 1
        except Exception as e:
            log.debug("insert avoid rec %s: %s", rec["ticker"], e)

    log.info("recommender: %d buy + %d avoid recommendations built (cycle %d)",
             len(buy_list), len(avoid_list), cycle_id)
    return total_inserted
