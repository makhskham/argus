const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"

export interface Recommendation {
  id: number
  ticker: string
  company_name: string | null
  direction: "buy" | "avoid"
  rank: number
  confidence: number
  bull_pct: number
  neutral_pct: number
  bear_pct: number
  signal_count: number
  source_count: number
  ai_analysis: string | null
  price_target_base: number | null
  price_target_bull: number | null
  price_target_bear: number | null
  halal_compliant: boolean | null
}

export interface Signal {
  id: number
  source: string
  source_type: string
  subreddit: string | null
  author: string | null
  title: string | null
  body: string
  url: string | null
  upvotes: number
  upvote_ratio: number
  posted_at: string
  tickers: string[]
  sentiment: "bullish" | "bearish" | "neutral" | null
  confidence: number | null
  key_quote: string | null
  is_niche_flagged: boolean | null
  trust_tier: "unverified" | "recognized" | "trusted" | "authority" | null
  halal_compliant: boolean | null
}

export async function fetchRecommendations(
  direction: "buy" | "avoid",
  halal = false,
  limit = 30
): Promise<Recommendation[]> {
  const url = new URL(`${API}/api/v1/recommendations`)
  url.searchParams.set("direction", direction)
  url.searchParams.set("halal", String(halal))
  url.searchParams.set("limit", String(limit))
  const res = await fetch(url.toString(), { next: { revalidate: 300 } })
  if (!res.ok) return []
  return res.json()
}

export async function fetchSignals(params: {
  ticker?: string
  sentiment?: string
  halal?: boolean
  since?: string
}): Promise<Signal[]> {
  const url = new URL(`${API}/api/v1/signals`)
  if (params.ticker) url.searchParams.set("ticker", params.ticker)
  if (params.sentiment) url.searchParams.set("sentiment", params.sentiment)
  if (params.halal) url.searchParams.set("halal", "true")
  if (params.since) url.searchParams.set("since", params.since)
  const res = await fetch(url.toString(), { next: { revalidate: 60 } })
  if (!res.ok) return []
  return res.json()
}

export async function fetchRecommendationByTicker(ticker: string) {
  const res = await fetch(`${API}/api/v1/recommendations/${ticker}`, {
    next: { revalidate: 300 },
  })
  if (!res.ok) return null
  return res.json()
}
