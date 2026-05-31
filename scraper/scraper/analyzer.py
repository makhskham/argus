"""
Signal analyzer — three tiers, uses the best available:

1. Claude Sonnet 4.6  (Anthropic) — best quality, ~$1 per 500 signals
2. Groq llama-3.3-70b (Groq)      — free tier, very good quality
3. Regex + keywords               — instant, no API, works offline

The system auto-selects based on which keys are available and have credits.
Set ANTHROPIC_API_KEY for Claude, GROQ_API_KEY for Groq, or neither for regex.
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
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")

CLAUDE_MODEL = "claude-sonnet-4-6"
GROQ_MODEL = "llama-3.3-70b-versatile"

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"

BATCH_SIZE = 10

# Session-level flag: once Claude is known out of credits, skip it entirely
_claude_out_of_credits = False

# Strong ticker pattern: $NVDA or all-caps 2-5 chars
TICKER_RE = re.compile(r'\$([A-Z]{1,5})\b')
TICKER_RE_BARE = re.compile(r'\b([A-Z]{2,5})\b')

EXCLUDE_WORDS = {
    "I", "A", "AN", "THE", "FOR", "AND", "BUT", "OR", "NOT", "IS", "IT",
    "TO", "OF", "IN", "ON", "AT", "BY", "UP", "IF", "NO", "SO", "DO",
    "GO", "BE", "AS", "WE", "HE", "ME", "US", "MY", "CEO", "CFO", "IPO",
    "ETF", "USD", "EUR", "GBP", "GDP", "CPI", "SEC", "FDA", "DOJ", "FTC",
    "FED", "NYSE", "OTC", "DD", "YOLO", "IMO", "TBH", "EPS", "PE", "FCF",
    "DCF", "EV", "EBITDA", "YOY", "QOQ", "FOMC", "SPY", "QQQ", "IWM",
    "VIX", "AI", "ML", "US", "UK", "EU", "CA", "AU", "RE", "ALL", "NEW",
    "NOW", "GET", "SET", "PUT", "CALL", "BUY", "SELL", "HIGH", "LOW",
    "OPEN", "THAT", "THIS", "WITH", "FROM", "HAVE", "BEEN", "THEY", "WILL",
    "JUST", "LIKE", "THAN", "WHEN", "WHAT", "YOUR", "ALSO", "INTO", "MORE",
    "SOME", "TIME", "YEAR", "VERY", "WELL", "THEN", "OVER", "BACK", "GOOD",
    "ONLY", "EVEN", "HERE", "LONG", "SUCH", "MOST", "BOTH", "AFTER", "STILL",
    "NEWS", "WEEK", "LAST", "NEXT", "HARD", "REAL", "FEEL", "EACH", "ELSE",
    "BEEN", "KNOW", "TAKE", "MAKE", "COME", "LOOK", "NEED", "MUCH", "WORK",
    "SAID", "SAME", "DOWN", "MOVE", "HELD", "HOLD", "RISK", "LOSS", "GAIN",
    "RATE", "CASH", "FUND", "DEBT", "PAID", "PLAN", "GROW", "BULL", "BEAR",
    "PUTS", "CALLS", "APES", "MOON", "FOMO", "HODL", "DIPS", "TOPS",
}

# Sentiment keywords for regex mode
BULL_WORDS = {
    "buy", "bullish", "long", "moon", "rocket", "pump", "surge", "rally",
    "undervalued", "cheap", "strong", "growth", "upside", "breakout",
    "opportunity", "catalyst", "potential", "beat", "earnings beat",
    "acquisition", "partnership", "deal", "contract", "approval", "win",
    "rise", "rising", "uptrend", "hidden gem", "accumulate", "dip",
    "oversold", "support", "squeeze", "momentum", "bullrun",
}

BEAR_WORDS = {
    "sell", "bearish", "short", "puts", "crash", "dump", "tank", "drop",
    "overvalued", "expensive", "weak", "decline", "downside", "breakdown",
    "avoid", "warning", "red flag", "fraud", "scam", "miss", "earnings miss",
    "lawsuit", "investigation", "scandal", "bankrupt", "debt", "loss",
    "fall", "falling", "downtrend", "danger", "risk", "concern", "worry",
    "overbought", "resistance", "short squeeze", "bubble", "dead",
}

SYSTEM_PROMPT = """You are a financial signal analyzer. Analyze Reddit/social media posts about stocks.

Return a JSON array, one object per post:
{
  "signal_id": <integer>,
  "tickers": ["NVDA", "MSFT"],
  "sentiment": "bullish|bearish|neutral",
  "confidence": 0-100,
  "key_quote": "<best sentence, max 150 chars>",
  "is_prediction": true/false,
  "prediction_direction": "up|down|null",
  "prediction_timeframe": "1 week|null",
  "is_niche_flagged": true/false
}

Confidence: 80-100=specific data-backed claim, 60-79=good reasoning, 40-59=general, 20-39=vague, 0-19=noise.
is_niche_flagged=true only for obscure small companies (<$2B market cap) rarely discussed.
Return ONLY the JSON array."""


def _extract_tickers_regex(text: str) -> list[str]:
    """Fast ticker extraction using regex. Prioritizes $TICKER format."""
    tickers = set()
    # First pass: $TICKER format (high confidence)
    for m in TICKER_RE.finditer(text):
        t = m.group(1).upper()
        if t not in EXCLUDE_WORDS and 1 <= len(t) <= 5:
            tickers.add(t)
    # Second pass: bare ALL-CAPS words (lower confidence, only if no $ tickers found)
    if not tickers:
        for m in TICKER_RE_BARE.finditer(text):
            t = m.group(1).upper()
            if t not in EXCLUDE_WORDS and 2 <= len(t) <= 5:
                tickers.add(t)
    return list(tickers)[:5]


def _score_sentiment_regex(text: str) -> tuple[str, int]:
    """Keyword-based sentiment scoring."""
    text_lower = text.lower()
    bull_score = sum(1 for w in BULL_WORDS if w in text_lower)
    bear_score = sum(1 for w in BEAR_WORDS if w in text_lower)

    if bull_score > bear_score and bull_score >= 2:
        confidence = min(30 + bull_score * 8, 65)
        return "bullish", confidence
    elif bear_score > bull_score and bear_score >= 2:
        confidence = min(30 + bear_score * 8, 65)
        return "bearish", confidence
    elif bull_score == 1:
        return "bullish", 25
    elif bear_score == 1:
        return "bearish", 25
    return "neutral", 20


def _analyze_regex(signals: list[dict]) -> list[dict]:
    """Pure regex analysis - no API needed. Works offline immediately."""
    results = []
    for sig in signals:
        text = f"{sig.get('title', '')} {sig.get('body', '')}".strip()
        tickers = _extract_tickers_regex(text)
        if not tickers:
            continue
        sentiment, confidence = _score_sentiment_regex(text)
        # Boost confidence for high-upvote posts
        upvotes = sig.get("upvotes", 0) or 0
        if upvotes > 100:
            confidence = min(confidence + 10, 75)
        if upvotes > 1000:
            confidence = min(confidence + 10, 80)
        results.append({
            "signal_id": sig["id"],
            "tickers": tickers,
            "sentiment": sentiment,
            "confidence": confidence,
            "key_quote": text[:150],
            "is_prediction": any(w in text.lower() for w in ["will", "target", "expect", "going to"]),
            "prediction_direction": "up" if sentiment == "bullish" else ("down" if sentiment == "bearish" else None),
            "prediction_timeframe": None,
            "is_niche_flagged": False,
        })
    return results


async def _call_ai_api(
    signals: list[dict],
    client: httpx.AsyncClient,
) -> list[dict]:
    """
    Call Claude or Groq API for high-quality analysis.
    Falls back automatically if one fails or has no credits.
    """
    content_parts = []
    for sig in signals:
        text = sig.get("title", "") or ""
        body = sig.get("body", "") or ""
        if body and body != text:
            text = f"{text}\n\n{body}" if text else body
        content_parts.append(
            f"[Signal ID: {sig['id']}] Source: {sig.get('source', 'unknown')}\n{text[:1500]}"
        )
    user_message = "\n\n---\n\n".join(content_parts)

    # Try Claude first (only if it has credits)
    if ANTHROPIC_KEY and not _claude_out_of_credits:
        try:
            r = await client.post(
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
            if r.status_code == 200:
                data = r.json()
                text_out = data["content"][0]["text"].strip()
                text_out = re.sub(r"```(?:json)?\n?", "", text_out).strip("`").strip()
                return json.loads(text_out)
            elif "credit balance is too low" in r.text or "insufficient" in r.text.lower():
                global _claude_out_of_credits
                _claude_out_of_credits = True
                log.warning("Claude: out of credits - switching permanently to Groq this session")
            else:
                log.warning("Claude error %d", r.status_code)
        except Exception as e:
            log.warning("Claude failed (%s)", e)

    # Groq (free tier) with retry backoff for rate limits
    if GROQ_KEY:
        for attempt in range(4):  # up to 4 retries
            try:
                r = await client.post(
                    GROQ_API,
                    headers={
                        "Authorization": f"Bearer {GROQ_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": user_message},
                        ],
                        "max_tokens": 4096,
                        "temperature": 0.1,
                    },
                    timeout=60,
                )
                if r.status_code == 200:
                    data = r.json()
                    text_out = data["choices"][0]["message"]["content"].strip()
                    text_out = re.sub(r"```(?:json)?\n?", "", text_out).strip("`").strip()
                    return json.loads(text_out)
                elif r.status_code == 429:
                    # Rate limited - wait longer before retry
                    wait = 3 * (attempt + 1)
                    log.debug("Groq rate limit, waiting %ds (attempt %d)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                else:
                    log.warning("Groq error %d", r.status_code)
                    break
            except Exception as e:
                log.warning("Groq failed (%s)", e)
                break

    return []  # All APIs failed, caller falls back to regex


async def check_groq_credits(client: httpx.AsyncClient) -> bool:
    """Quick check if Groq key is valid and has quota."""
    if not GROQ_KEY:
        return False
    try:
        r = await client.post(
            GROQ_API,
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False


async def run_analysis(
    conn: asyncpg.Connection,
    hours_back: int = 72,
    max_signals: int = 300,
) -> int:
    """
    Analyze ONLY unprocessed signals (never re-analyzes the same signal twice).

    Priority order for time windows (saves tokens):
    - First: signals from last 3 days (freshest, most actionable)
    - Then: up to last 7 days if budget allows
    - Then: up to last 14 days if budget still allows

    Signals already in signal_analyses are skipped entirely.
    The most upvoted signals are processed first (highest signal quality per token).
    """
    now = datetime.now(tz=timezone.utc)

    # Priority time windows - process freshest first, expand if tokens allow
    time_windows = [
        timedelta(days=3),   # Priority 1: last 3 days
        timedelta(days=7),   # Priority 2: last week
        timedelta(days=14),  # Priority 3: last 2 weeks
        timedelta(days=30),  # Priority 4: last month (only if well within limits)
    ]

    # Use the requested hours_back as a cap
    cap = timedelta(hours=hours_back)
    windows = [w for w in time_windows if w <= cap]
    if not windows:
        windows = [cap]

    # Fetch unanalyzed signals within the priority window
    # Start with the tightest window (3 days)
    since = now - windows[0]

    rows = await conn.fetch("""
        SELECT s.id, s.source, s.source_type, s.subreddit, s.author,
               s.title, s.body, s.upvotes, s.upvote_ratio, s.posted_at
        FROM signals s
        WHERE s.posted_at >= $1
          AND NOT EXISTS (
              SELECT 1 FROM signal_analyses sa WHERE sa.signal_id = s.id
          )
          AND LENGTH(s.body) >= 30
        ORDER BY s.upvotes DESC, s.posted_at DESC
        LIMIT $2
    """, since, max_signals)

    # If we have budget headroom and not many signals in the tight window, expand
    if len(rows) < 50 and len(windows) > 1:
        since = now - windows[1]
        rows = await conn.fetch("""
            SELECT s.id, s.source, s.source_type, s.subreddit, s.author,
                   s.title, s.body, s.upvotes, s.upvote_ratio, s.posted_at
            FROM signals s
            WHERE s.posted_at >= $1
              AND NOT EXISTS (
                  SELECT 1 FROM signal_analyses sa WHERE sa.signal_id = s.id
              )
              AND LENGTH(s.body) >= 30
            ORDER BY s.upvotes DESC, s.posted_at DESC
            LIMIT $2
        """, since, max_signals)

    if not rows:
        log.info("analysis: no unprocessed signals found (all already analyzed)")
        return 0

    signals = [dict(r) for r in rows]

    # Deduplicate by body content to avoid re-analyzing near-identical posts
    seen_bodies: set[str] = set()
    unique_signals = []
    for sig in signals:
        body_key = (sig.get("body") or "")[:100].strip().lower()
        if body_key and body_key not in seen_bodies:
            seen_bodies.add(body_key)
            unique_signals.append(sig)
    signals = unique_signals

    use_ai = bool(ANTHROPIC_KEY or GROQ_KEY)
    mode = "Claude" if ANTHROPIC_KEY else ("Groq/llama-3.3-70b (free)" if GROQ_KEY else "regex (no API)")
    log.info("analysis: %d unique unprocessed signals → %s", len(signals), mode)

    analyzed = 0

    async def _store(results: list[dict], model_label: str) -> int:
        count = 0
        for result in results:
            signal_id = result.get("signal_id")
            if not signal_id:
                continue
            tickers = [
                t.upper().strip("$")
                for t in (result.get("tickers") or [])
                if t and 1 <= len(t.strip("$")) <= 5
                and t.strip("$").upper() not in EXCLUDE_WORDS
            ]
            if not tickers:
                continue
            sentiment = result.get("sentiment", "neutral")
            if sentiment not in ("bullish", "bearish", "neutral"):
                sentiment = "neutral"
            confidence = max(0, min(100, int(result.get("confidence", 40))))
            key_quote = (result.get("key_quote") or "")[:500]
            try:
                await conn.execute("""
                    INSERT INTO signal_analyses
                      (signal_id, tickers, sentiment, confidence, key_quote,
                       is_prediction, prediction_direction, prediction_timeframe,
                       is_niche_flagged, model_used)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT DO NOTHING
                """, signal_id, tickers, sentiment, confidence, key_quote,
                    bool(result.get("is_prediction")),
                    result.get("prediction_direction"),
                    result.get("prediction_timeframe"),
                    bool(result.get("is_niche_flagged")),
                    model_label)
                count += 1
            except Exception as e:
                log.debug("store analysis %s: %s", signal_id, e)
        return count

    if use_ai:
        async with httpx.AsyncClient() as client:
            for i in range(0, len(signals), BATCH_SIZE):
                batch = signals[i:i + BATCH_SIZE]
                results = await _call_ai_api(batch, client)
                if results:
                    n = await _store(results, CLAUDE_MODEL if ANTHROPIC_KEY else GROQ_MODEL)
                    analyzed += n
                else:
                    # AI failed for this batch - use regex fallback
                    regex_results = _analyze_regex(batch)
                    n = await _store(regex_results, "regex")
                    analyzed += n
                log.info("  batch %d-%d: %d analyses stored",
                         i + 1, min(i + BATCH_SIZE, len(signals)), analyzed)
                # Groq free tier: 30 req/min. Sleep 2s between batches to stay under limit.
                await asyncio.sleep(2)
    else:
        # Pure regex mode - fast, no API needed
        log.info("analysis: using regex mode (set GROQ_API_KEY for free AI analysis)")
        for i in range(0, len(signals), 50):
            batch = signals[i:i + 50]
            results = _analyze_regex(batch)
            n = await _store(results, "regex")
            analyzed += n
        log.info("  regex: %d analyses from %d signals", analyzed, len(signals))

    log.info("analysis complete: %d analyses stored", analyzed)
    return analyzed
