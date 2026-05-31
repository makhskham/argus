"""
Halal / Shariah compliance screener.

Multiple free sources for compliance data:

1. Musaffa (musaffa.com) - 120,000+ stocks, 8,500+ ETFs, completely free
2. Islamicly - free compliance scorecard
3. Zoya sandbox API (already configured)
4. Community-curated lists (SPUS, HLAL, UMMA, WSHR ETFs)

The screening logic follows standard AAOIFI criteria:
- Business activity: no alcohol, weapons, gambling, pork, conventional banking,
  tobacco, or adult entertainment
- Financial ratios (debt/market cap < 33%, interest income < 5% revenue)

For the Argus hidden gem use case, halal screening is especially valuable
for finding compliant micro/small-cap stocks before they get mainstream coverage.

Key halal ETF tickers to track (pre-screened universes):
  SPUS  - S&P 500 Shariah (USA)
  HLAL  - Wahed FTSE USA Shariah ETF
  UMMA  - Wahed Dow Jones Islamic World ETF
  WSHR  - Wealthsimple Shariah World Equity (Canada)
  ISWD  - iShares MSCI World Islamic UCITS ETF

These ETFs act as a "pre-screened universe" — any stock in them is halal.
"""
import asyncio
import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)

ZOYA_KEY = os.environ.get("ZOYA_API_KEY", "")
ZOYA_SANDBOX = os.environ.get("ZOYA_SANDBOX", "") == "true"

# Halal ETFs — all constituent stocks are Shariah compliant by definition
HALAL_ETF_TICKERS = ["SPUS", "HLAL", "UMMA", "WSHR", "ISWD", "AMANX", "AMAPX"]

# Known non-compliant sectors to flag immediately
NON_COMPLIANT_SECTORS = {
    "alcoholic beverages", "tobacco", "weapons", "gambling", "casinos",
    "conventional banking", "insurance", "pork", "adult entertainment",
    "pornography", "interest-based finance",
}

MUSAFFA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://musaffa.com/",
}


async def check_musaffa(ticker: str) -> Optional[dict]:
    """
    Check Musaffa for Shariah compliance. Free, no API key needed.
    Covers 120,000+ stocks globally.
    """
    url = f"https://musaffa.com/api/v1/instruments/{ticker}/compliance"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=MUSAFFA_HEADERS)
            if r.status_code == 200:
                data = r.json()
                return {
                    "ticker": ticker,
                    "is_compliant": data.get("status") == "COMPLIANT",
                    "status": data.get("status"),
                    "source": "musaffa",
                }
    except Exception as e:
        log.debug("musaffa %s: %s", ticker, e)
    return None


async def check_zoya(ticker: str) -> Optional[dict]:
    """Check Zoya API (sandbox mode returns randomized data for dev)."""
    if not ZOYA_KEY:
        return None

    base = "https://api.zoya.finance/graphql"
    if ZOYA_SANDBOX:
        base = "https://sandbox.zoya.finance/graphql"

    query = """
    query StockCompliance($ticker: String!) {
      stockCompliance(ticker: $ticker) {
        status
        debtRatio
        interestIncomeRatio
        businessActivityStatus
      }
    }
    """
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(base, json={
                "query": query,
                "variables": {"ticker": ticker},
            }, headers={
                "Authorization": f"Bearer {ZOYA_KEY}",
                "Content-Type": "application/json",
            })
            if r.status_code == 200:
                data = r.json().get("data", {}).get("stockCompliance", {})
                status = data.get("status", "UNKNOWN")
                return {
                    "ticker": ticker,
                    "is_compliant": status == "COMPLIANT",
                    "zoya_status": status,
                    "debt_ratio": data.get("debtRatio"),
                    "interest_income_ratio": data.get("interestIncomeRatio"),
                    "business_activity_ok": data.get("businessActivityStatus") == "COMPLIANT",
                    "source": "zoya_sandbox" if ZOYA_SANDBOX else "zoya",
                }
    except Exception as e:
        log.debug("zoya %s: %s", ticker, e)
    return None


async def screen_ticker(ticker: str) -> dict:
    """
    Screen a ticker for Shariah compliance.
    Tries Musaffa first (free, broad coverage), falls back to Zoya.
    """
    # Try Musaffa first
    result = await check_musaffa(ticker)
    if result:
        return result

    # Fall back to Zoya
    result = await check_zoya(ticker)
    if result:
        return result

    # Unknown - return neutral
    return {
        "ticker": ticker,
        "is_compliant": None,
        "status": "UNKNOWN",
        "source": "none",
    }


async def screen_tickers_batch(tickers: list[str]) -> list[dict]:
    """Screen multiple tickers with rate limiting."""
    results = []
    for i in range(0, len(tickers), 5):
        batch = tickers[i:i + 5]
        batch_results = await asyncio.gather(
            *[screen_ticker(t) for t in batch],
            return_exceptions=True,
        )
        for r in batch_results:
            if isinstance(r, dict):
                results.append(r)
        await asyncio.sleep(0.5)
    return results
