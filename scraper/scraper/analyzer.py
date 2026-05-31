"""
Claude signal analyzer.

Reads raw scraped signals from the database in batches, sends them to
Claude Sonnet 4.6 for analysis, and stores structured results in signal_analyses.

Claude extracts per-signal:
- Which stock tickers are mentioned
- Sentiment (bullish / bearish / neutral)
- Confidence score (0-100)
- Key quote (most insightful sentence)
- Whether it contains a price prediction
- Whether it's a niche/overlooked insight

This is what transforms raw text into the ranked recommendations on the dashboard.
"""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta

import asyncpg
import httpx

log = logging.getLogger(__name__)

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"

# Batch size - how many signals to send to Claude at once
BATCH_SIZE = 10

# Well-known ticker pattern
TICKER_RE = re.compile(r'\b\$([A-Z]{1,5})\b|\b([A-Z]{2,5})\b')

# Words that look like tickers but aren't
EXCLUDE_WORDS = {
    "I", "A", "AN", "THE", "FOR", "AND", "BUT", "OR", "NOT", "IS", "IT",
    "TO", "OF", "IN", "ON", "AT", "BY", "UP", "IF", "NO", "SO", "DO",
    "GO", "BE", "AS", "WE", "HE", "ME", "US", "MY", "CEO", "CFO", "IPO",
    "ETF", "USD", "EUR", "GDP", "CPI", "SEC", "FDA", "DOJ", "FTC", "FED",
    "NYSE", "OTC", "DD", "YOLO", "IMO", "TBH", "EPS", "PE", "FCF", "DCF",
    "EV", "EBITDA", "YOY", "QOQ", "FOMC", "SPY", "QQQ", "IWM", "VIX",
    "AI", "ML", "US", "UK", "EU", "CA", "AU", "RE", "ALL", "NEW", "NOW",
    "GET", "SET", "PUT", "CALL", "BUY", "SELL", "HIGH", "LOW", "OPEN",
}


SYSTEM_PROMPT = """You are a financial signal analyzer for Argus, an investment intelligence platform.

Analyze the provided Reddit/social media posts about stocks and markets.
For each post, extract structured investment signals.

Return a JSON array with one object per post analyzed.
Each object must have these exact fields:
{
  "signal_id": <integer from input>,
  "tickers": [<list of stock ticker symbols mentioned, e.g. ["NVDA", "MSFT"]>],
  "sentiment": "<bullish|bearish|neutral>",
  "confidence": <integer 0-100>,
  "key_quote": "<the single most insightful/actionable sentence from the post, max 200 chars>",
  "is_prediction": <true if author makes a directional price prediction, false otherwise>,
  "prediction_direction": "<up|down|null>",
  "prediction_timeframe": "<e.g. '1 week', '3 months', null>",
  "is_niche_flagged": <true if this discusses an obscure/overlooked company most people don't know>
}

Confidence scoring guide:
- 90-100: Highly specific, data-backed, from clearly knowledgeable source
- 70-89: Good reasoning, specific claims, relevant to investment decision
- 50-69: General discussion, some useful information
- 30-49: Vague or mostly noise
- 0-29: No actionable signal

Rules:
- Only include tickers that are clearly stock tickers (1-5 uppercase letters), not abbreviations
- Skip posts with no investment signal (return empty tickers, sentiment=neutral, confidence=0-20)
- is_niche_flagged=true only for small/obscure companies with <$5B market cap or very low Reddit coverage
- Return ONLY the JSON array, no other text"""


async def analyze_batch(
    signals: list[dict],
    client: httpx.AsyncClient,
) -> list[dict]:
    """Send a batch of signals to Claude for analysis."""
    if not ANTHROPIC_KEY:
        log.warning("ANTHROPIC_API_KEY not set - skipping analysis")
        return []

    # Build the message content
    content_parts = []
    for sig in signals:
        text = sig.get("title", "") or ""
        body = sig.get("body", "") or ""
        if body and body != text:
            text = f"{text}\n\n{body}" if text else body
        text = text[:2000]  # cap per signal
        content_parts.append(
            f"[Signal ID: {sig['id']}] Source: {sig.get('source', 'unknown')}\n{text}"
        )

    user_message = "\n\n---\n\n".join(content_parts)

    try:
        response = await client.post(
            ANTHROPIC_API,
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 4096,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=60,
        )

        if response.status_code != 200:
            log.warning("Claude API error %d: %s", response.status_code, response.text[:200])
            return []

        data = response.json()
        text_content = data["content"][0]["text"]

        # Parse JSON from response
        # Claude sometimes wraps in ```json ``` - strip that
        text_content = text_content.strip()
        if text_content.startswith("```"):
            text_content = re.sub(r"```(?:json)?\n?", "", text_content).strip("`").strip()

        analyses = json.loads(text_content)
        return analyses if isinstance(analyses, list) else []

    except json.JSONDecodeError as e:
        log.warning("Claude response not valid JSON: %s", e)
        return []
    except Exception as e:
        log.warning("Claude analysis batch failed: %s", e)
        return []


async def run_analysis(
    conn: asyncpg.Connection,
    hours_back: int = 48,
    max_signals: int = 500,
) -> int:
    """
    Analyze unprocessed signals from the last N hours.
    Returns count of signals analyzed.
    """
    if not ANTHROPIC_KEY:
        log.warning("ANTHROPIC_API_KEY not set - cannot run analysis")
        return 0

    since = datetime.now(tz=timezone.utc) - timedelta(hours=hours_back)

    # Fetch unanalyzed signals
    rows = await conn.fetch("""
        SELECT s.id, s.source, s.source_type, s.subreddit, s.author,
               s.title, s.body, s.upvotes, s.upvote_ratio, s.posted_at
        FROM signals s
        WHERE s.scraped_at >= $1
          AND NOT EXISTS (
              SELECT 1 FROM signal_analyses sa WHERE sa.signal_id = s.id
          )
          AND LENGTH(s.body) >= 30
        ORDER BY s.upvotes DESC, s.scraped_at DESC
        LIMIT $2
    """, since, max_signals)

    if not rows:
        log.info("analysis: no unprocessed signals found")
        return 0

    signals = [dict(r) for r in rows]
    log.info("analysis: processing %d signals with Claude %s", len(signals), CLAUDE_MODEL)

    analyzed = 0
    async with httpx.AsyncClient() as client:
        for i in range(0, len(signals), BATCH_SIZE):
            batch = signals[i:i + BATCH_SIZE]
            analyses = await analyze_batch(batch, client)

            for result in analyses:
                signal_id = result.get("signal_id")
                if not signal_id:
                    continue

                tickers = [
                    t.upper().strip("$")
                    for t in (result.get("tickers") or [])
                    if t and len(t.strip("$")) <= 5
                    and t.strip("$").upper() not in EXCLUDE_WORDS
                ]
                if not tickers:
                    continue  # skip signals with no identified tickers

                sentiment = result.get("sentiment", "neutral")
                if sentiment not in ("bullish", "bearish", "neutral"):
                    sentiment = "neutral"

                confidence = max(0, min(100, int(result.get("confidence", 50))))
                key_quote = (result.get("key_quote") or "")[:500]
                is_prediction = bool(result.get("is_prediction", False))
                pred_dir = result.get("prediction_direction")
                pred_time = result.get("prediction_timeframe")
                is_niche = bool(result.get("is_niche_flagged", False))

                try:
                    await conn.execute("""
                        INSERT INTO signal_analyses
                          (signal_id, tickers, sentiment, confidence, key_quote,
                           is_prediction, prediction_direction, prediction_timeframe,
                           is_niche_flagged, model_used)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        ON CONFLICT DO NOTHING
                    """, signal_id, tickers, sentiment, confidence, key_quote,
                        is_prediction, pred_dir, pred_time, is_niche, CLAUDE_MODEL)
                    analyzed += 1
                except Exception as e:
                    log.debug("insert analysis failed signal %s: %s", signal_id, e)

            log.info("  analyzed batch %d-%d (%d tickers found)",
                     i + 1, min(i + BATCH_SIZE, len(signals)), analyzed)
            await asyncio.sleep(0.5)  # avoid rate limits

    log.info("analysis complete: %d/%d signals produced ticker data", analyzed, len(signals))
    return analyzed
