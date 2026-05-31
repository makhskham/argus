# Argus Phase 2: Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** Build the complete Argus frontend — Command Center dashboard, Intelligence Feed, Stock Deep Dive, Date Explorer, AI Chat, and Profile pages — with the full monochromatic design system (black/grey/white, green/red semantic colors, ☽ halal symbols).

**Architecture:** Next.js 15 App Router. TanStack Query for API calls to Go backend (localhost:8080). Vercel AI SDK for streaming chat. nuqs for URL state. All pages under app/(app)/ route group with Sidebar already implemented.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query v5, Vercel AI SDK, lightweight-charts, Framer Motion, Clerk, nuqs

**Design system:**
- bg-black (#000), surface #080808, border #161616
- Text: white primary, #94a3b8 secondary, #4b5563 muted, #2d2d2d dim
- Active/brand accent: #e2e8f0 (silver-white)
- Bull: #22c55e, Bear: #ef4444, Neutral: #f59e0b
- Halal: ☽ symbol in #22c55e
- Cards: bg-[#080808] border border-[#161616] rounded-lg
- Trust tiers: Authority=silver (#e2e8f0), Trusted=green, Recognized=amber

---

## Task 1: Shared UI components

**Files:**
- Create: `web/components/ui/stat-card.tsx`
- Create: `web/components/ui/signal-card.tsx`
- Create: `web/components/ui/ticker-badge.tsx`
- Create: `web/components/ui/trust-badge.tsx`
- Create: `web/components/ui/sentiment-bar.tsx`
- Create: `web/lib/api.ts`

- [ ] Create `web/lib/api.ts`:
```typescript
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
```

- [ ] Create `web/components/ui/stat-card.tsx`:
```tsx
interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  valueColor?: string
}

export function StatCard({ label, value, sub, valueColor = "text-white" }: StatCardProps) {
  return (
    <div className="bg-[#080808] border border-[#161616] rounded-lg p-4 relative overflow-hidden">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "linear-gradient(135deg, rgba(148,163,184,0.015) 0%, transparent 60%)",
        }}
      />
      <div className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase mb-1.5">
        {label}
      </div>
      <div className={`text-2xl font-bold leading-none ${valueColor}`}>
        {value}
      </div>
      {sub && <div className="text-[11px] text-[#2d2d2d] mt-1">{sub}</div>}
    </div>
  )
}
```

- [ ] Create `web/components/ui/ticker-badge.tsx`:
```tsx
interface TickerBadgeProps {
  ticker: string
  halalCompliant?: boolean | null
}

export function TickerBadge({ ticker, halalCompliant }: TickerBadgeProps) {
  return (
    <span className="flex items-center gap-1">
      <span className="font-mono font-bold text-white tracking-wide">
        {ticker}
      </span>
      {halalCompliant && (
        <span
          className="text-[#22c55e] text-xs"
          title="Shariah Compliant — verified by Zoya / DJIMI"
        >
          ☽
        </span>
      )}
    </span>
  )
}
```

- [ ] Create `web/components/ui/trust-badge.tsx`:
```tsx
const TIERS = {
  authority: {
    label: "AUTHORITY",
    className: "bg-[#161616] text-[#e2e8f0] border border-[#2a2a2a]",
  },
  trusted: {
    label: "TRUSTED",
    className: "bg-[#041008] text-[#22c55e] border border-[#0a2010]",
  },
  recognized: {
    label: "RECOGNIZED",
    className: "bg-[#120d00] text-[#f59e0b] border border-[#2a1e00]",
  },
  unverified: null,
}

interface TrustBadgeProps {
  tier: string | null | undefined
}

export function TrustBadge({ tier }: TrustBadgeProps) {
  if (!tier || tier === "unverified") return null
  const config = TIERS[tier as keyof typeof TIERS]
  if (!config) return null
  return (
    <span
      className={`text-[9px] font-bold tracking-[0.06em] px-1.5 py-0.5 rounded ${config.className}`}
    >
      {config.label}
    </span>
  )
}
```

- [ ] Create `web/components/ui/sentiment-bar.tsx`:
```tsx
interface SentimentBarProps {
  bull: number
  neutral: number
  bear: number
}

export function SentimentBar({ bull, neutral, bear }: SentimentBarProps) {
  return (
    <div className="flex items-center gap-1 text-[11px]">
      <span className="text-[#22c55e] font-medium">{Math.round(bull)}%</span>
      <span className="text-[#1c1c1c]">·</span>
      <span className="text-[#f59e0b]">{Math.round(neutral)}%</span>
      <span className="text-[#1c1c1c]">·</span>
      <span className="text-[#ef4444]">{Math.round(bear)}%</span>
    </div>
  )
}
```

- [ ] Create `web/components/ui/signal-card.tsx`:
```tsx
import { TrustBadge } from "./trust-badge"
import { TickerBadge } from "./ticker-badge"
import { Signal } from "@/lib/api"

const SENTIMENT_LABEL = {
  bullish: { text: "Bullish", className: "bg-[#041008] text-[#22c55e]" },
  bearish: { text: "Bearish", className: "bg-[#140305] text-[#ef4444]" },
  neutral: { text: "Neutral", className: "bg-[#120d00] text-[#f59e0b]" },
}

interface SignalCardProps {
  signal: Signal
  compact?: boolean
}

export function SignalCard({ signal, compact }: SignalCardProps) {
  const sentConf = signal.sentiment ? SENTIMENT_LABEL[signal.sentiment] : null
  const ago = signal.posted_at
    ? Math.round(
        (Date.now() - new Date(signal.posted_at).getTime()) / 3_600_000
      ) + "h ago"
    : ""

  return (
    <div className="px-4 py-3 border-b border-[#0d0d0d] hover:bg-[#050505] transition-colors">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {signal.tickers?.slice(0, 3).map((t) => (
          <TickerBadge
            key={t}
            ticker={t}
            halalCompliant={signal.halal_compliant}
          />
        ))}
        <span className="text-[10px] bg-[#111] border border-[#161616] rounded px-1.5 py-0.5 text-[#4b5563]">
          {signal.source}
        </span>
        {sentConf && (
          <span
            className={`text-[10px] rounded px-1.5 py-0.5 font-semibold ${sentConf.className}`}
          >
            {sentConf.text}
          </span>
        )}
        {signal.trust_tier && signal.trust_tier !== "unverified" && (
          <TrustBadge tier={signal.trust_tier} />
        )}
        <span className="text-[10px] text-[#1c1c1c] ml-auto">{ago}</span>
      </div>

      {!compact && (
        <p className="text-[12px] text-[#4b5563] leading-relaxed italic mb-2 line-clamp-3">
          {signal.key_quote || signal.body.slice(0, 240)}
        </p>
      )}

      <div className="flex items-center gap-3">
        {signal.confidence != null && (
          <div className="flex items-center gap-1.5">
            <div className="w-16 h-[3px] bg-[#161616] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${signal.confidence}%`,
                  background:
                    signal.confidence >= 70
                      ? "#22c55e"
                      : signal.confidence >= 50
                      ? "#f59e0b"
                      : "#ef4444",
                }}
              />
            </div>
            <span
              className={`text-[11px] font-bold font-mono ${
                signal.confidence >= 70
                  ? "text-[#22c55e]"
                  : signal.confidence >= 50
                  ? "text-[#f59e0b]"
                  : "text-[#ef4444]"
              }`}
            >
              {signal.confidence}
            </span>
          </div>
        )}
        {signal.upvotes > 0 && (
          <span className="text-[11px] text-[#2d2d2d]">
            ↑ {signal.upvotes.toLocaleString()}
          </span>
        )}
        {signal.is_niche_flagged && (
          <span className="text-[9px] bg-[#1a1208] text-[#d97706] rounded px-1.5 py-0.5">
            ★ niche insight
          </span>
        )}
        {signal.url && (
          <a
            href={signal.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-[#1c1c1c] hover:text-[#94a3b8] ml-auto transition-colors"
          >
            View →
          </a>
        )}
      </div>
    </div>
  )
}
```

- [ ] Commit:
```bash
cd "C:/Users/makhs/Desktop/Projects/Argus" && git add web/lib/api.ts web/components/ui/stat-card.tsx web/components/ui/signal-card.tsx web/components/ui/ticker-badge.tsx web/components/ui/trust-badge.tsx web/components/ui/sentiment-bar.tsx && git commit -m "feat: shared ui components and api client"
```

---

## Task 2: Command Center (Dashboard)

**Files:**
- Create: `web/components/recommendation-row.tsx`
- Create: `web/components/recommendation-table.tsx`
- Create: `web/components/breaking-signals-panel.tsx`
- Modify: `web/app/(app)/dashboard/page.tsx`

- [ ] Create `web/components/recommendation-row.tsx`:
```tsx
import Link from "next/link"
import { Recommendation } from "@/lib/api"
import { TickerBadge } from "./ui/ticker-badge"
import { TrustBadge } from "./ui/trust-badge"
import { SentimentBar } from "./ui/sentiment-bar"

interface Props {
  rec: Recommendation
  index: number
}

export function RecommendationRow({ rec, index }: Props) {
  const rank = index + 1
  const isBuy = rec.direction === "buy"
  const confColor =
    rec.confidence >= 70
      ? "#22c55e"
      : rec.confidence >= 50
      ? "#f59e0b"
      : "#ef4444"

  return (
    <Link
      href={`/stocks/${rec.ticker}`}
      className="grid items-center gap-2 px-4 py-2.5 border-b border-[#0a0a0a] hover:bg-[#0a0a0a] transition-colors cursor-pointer"
      style={{
        gridTemplateColumns: "28px 1fr 110px 110px 90px 70px",
      }}
    >
      <div
        className={`text-xs font-mono font-bold text-center ${
          rank <= 3 ? "text-[#e2e8f0]" : "text-[#1c1c1c]"
        }`}
      >
        {rank}
      </div>

      <div className="min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <TickerBadge ticker={rec.ticker} halalCompliant={rec.halal_compliant} />
        </div>
        {rec.company_name && (
          <div className="text-[10px] text-[#2d2d2d] truncate mt-0.5">
            {rec.company_name}
          </div>
        )}
      </div>

      <div className="flex items-center gap-1.5">
        <div className="flex-1 h-[3px] bg-[#161616] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{ width: `${rec.confidence}%`, background: confColor }}
          />
        </div>
        <span
          className="text-xs font-bold font-mono w-6 text-right"
          style={{ color: confColor }}
        >
          {rec.confidence}
        </span>
      </div>

      <SentimentBar bull={rec.bull_pct} neutral={rec.neutral_pct} bear={rec.bear_pct} />

      <div className="text-[10px] text-[#2d2d2d] text-right">
        {rec.signal_count.toLocaleString()}
        <br />
        <span className="text-[#1c1c1c]">{rec.source_count} src</span>
      </div>

      <div
        className={`text-xs font-bold font-mono text-right ${
          isBuy ? "text-[#22c55e]" : "text-[#ef4444]"
        }`}
      >
        —
      </div>
    </Link>
  )
}
```

- [ ] Create `web/components/recommendation-table.tsx`:
```tsx
"use client"
import { useQuery } from "@tanstack/react-query"
import { fetchRecommendations, Recommendation } from "@/lib/api"
import { RecommendationRow } from "./recommendation-row"

interface Props {
  direction: "buy" | "avoid"
  halal: boolean
  limit?: number
}

export function RecommendationTable({ direction, halal, limit = 30 }: Props) {
  const { data, isLoading, error } = useQuery<Recommendation[]>({
    queryKey: ["recommendations", direction, halal, limit],
    queryFn: () => fetchRecommendations(direction, halal, limit),
  })

  const label = direction === "buy" ? "BUY SIGNALS" : "AVOID / BEARISH"
  const arrow = direction === "buy" ? "▲" : "▼"
  const arrowColor = direction === "buy" ? "text-[#22c55e]" : "text-[#ef4444]"

  return (
    <div className="bg-[#080808] border border-[#161616] rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-[#111] bg-[#050505]">
        <span className={`text-[10px] font-bold ${arrowColor}`}>{arrow}</span>
        <span className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase">
          TOP {limit} — {label} · ranked by confidence score
        </span>
      </div>

      <div
        className="grid px-4 py-2 border-b border-[#0d0d0d] text-[9px] text-[#2d2d2d] tracking-[0.1em] uppercase"
        style={{ gridTemplateColumns: "28px 1fr 110px 110px 90px 70px" }}
      >
        <div>#</div>
        <div>Ticker</div>
        <div>Confidence</div>
        <div>Sentiment</div>
        <div className="text-right">Sources</div>
        <div className="text-right">7d Δ</div>
      </div>

      {isLoading && (
        <div className="px-4 py-8 text-center text-[#2d2d2d] text-xs">
          Loading...
        </div>
      )}
      {error && (
        <div className="px-4 py-8 text-center text-[#4b5563] text-xs">
          API not reachable — start the Go backend
        </div>
      )}
      {data?.map((rec, i) => (
        <RecommendationRow key={rec.id} rec={rec} index={i} />
      ))}
      {data?.length === 0 && !isLoading && (
        <div className="px-4 py-8 text-center text-[#2d2d2d] text-xs">
          No data yet — run a scrape cycle first
        </div>
      )}
    </div>
  )
}
```

- [ ] Create `web/components/breaking-signals-panel.tsx`:
```tsx
"use client"
import { useQuery } from "@tanstack/react-query"
import { fetchSignals, Signal } from "@/lib/api"
import { SignalCard } from "./ui/signal-card"

export function BreakingSignalsPanel() {
  const { data } = useQuery<Signal[]>({
    queryKey: ["signals", "breaking"],
    queryFn: () => fetchSignals({}),
    refetchInterval: 60_000,
  })

  const top = data?.slice(0, 5) ?? []

  return (
    <div className="bg-[#080808] border border-[#161616] rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#111]">
        <div className="text-[10px] font-bold text-[#4b5563] tracking-[0.1em] uppercase">
          Breaking Signals
        </div>
        <a
          href="/intelligence"
          className="text-[10px] text-[#2d2d2d] hover:text-[#94a3b8] transition-colors"
        >
          View all →
        </a>
      </div>
      {top.length === 0 ? (
        <div className="px-4 py-6 text-center text-[#2d2d2d] text-xs">
          No signals yet
        </div>
      ) : (
        top.map((s) => <SignalCard key={s.id} signal={s} compact />)
      )}
    </div>
  )
}
```

- [ ] Replace `web/app/(app)/dashboard/page.tsx`:
```tsx
"use client"
import { parseAsBoolean, parseAsString, useQueryStates } from "nuqs"
import { StatCard } from "@/components/ui/stat-card"
import { RecommendationTable } from "@/components/recommendation-table"
import { BreakingSignalsPanel } from "@/components/breaking-signals-panel"

export default function DashboardPage() {
  const [params, setParams] = useQueryStates({
    halal: parseAsBoolean.withDefault(false),
    tab: parseAsString.withDefault("all"),
  })

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Topbar */}
      <div className="flex items-center gap-4 px-6 py-3 border-b border-[#111] bg-black/80 backdrop-blur-sm flex-shrink-0">
        <div>
          <div className="text-sm font-bold text-white tracking-[0.04em]">
            Command Center
          </div>
          <div className="text-[10px] text-[#2d2d2d]">
            {params.halal ? "Shariah Compliant" : "All Markets"} · Last 7 days
          </div>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex bg-[#080808] border border-[#161616] rounded-md p-0.5">
            <button
              onClick={() => setParams({ tab: "all", halal: false })}
              className={`px-3 py-1.5 rounded text-xs transition-colors ${
                !params.halal
                  ? "bg-[#111] text-white border border-[#2a2a2a]"
                  : "text-[#4b5563] hover:text-[#94a3b8]"
              }`}
            >
              All Markets
            </button>
            <button
              onClick={() => setParams({ tab: "halal", halal: true })}
              className={`px-3 py-1.5 rounded text-xs transition-colors flex items-center gap-1 ${
                params.halal
                  ? "bg-[#041008] text-[#22c55e] border border-[#0a2010]"
                  : "text-[#4b5563] hover:text-[#94a3b8]"
              }`}
            >
              <span>☽</span> Shariah Compliant
            </button>
          </div>
          <div className="text-[10px] text-[#2d2d2d] flex items-center gap-1.5">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#22c55e] animate-pulse" />
            Live
          </div>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-4">
          {/* Stat cards */}
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="Market Sentiment" value="—" sub="Awaiting data" />
            <StatCard label="Posts Analyzed" value="—" sub="Run scraper first" />
            <StatCard label="High-Conf Signals" value="—" sub="Confidence > 80" />
            <StatCard
              label="Halal Picks"
              value="☽ —"
              sub="Shariah compliant"
              valueColor="text-[#22c55e]"
            />
          </div>

          {/* Main content */}
          <div className="grid grid-cols-[1fr_320px] gap-4">
            <div className="space-y-4">
              <RecommendationTable direction="buy" halal={params.halal} />
              <RecommendationTable direction="avoid" halal={params.halal} />
            </div>
            <div>
              <BreakingSignalsPanel />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] Commit:
```bash
cd "C:/Users/makhs/Desktop/Projects/Argus" && git add web/ && git commit -m "feat: command center dashboard with recommendation tables and signals panel"
```

---

## Task 3: Intelligence Feed page

**Files:**
- Modify: `web/app/(app)/intelligence/page.tsx`

- [ ] Replace `web/app/(app)/intelligence/page.tsx`:
```tsx
"use client"
import { parseAsBoolean, parseAsString, useQueryStates } from "nuqs"
import { useQuery } from "@tanstack/react-query"
import { fetchSignals, Signal } from "@/lib/api"
import { SignalCard } from "@/components/ui/signal-card"

const SENTIMENTS = ["", "bullish", "bearish", "neutral"]
const SOURCES = [
  "r/SecurityAnalysis", "r/wallstreetbets", "r/algotrading",
  "r/stocks", "r/investing", "r/ValueInvesting", "SEC EDGAR",
]

export default function IntelligencePage() {
  const [params, setParams] = useQueryStates({
    ticker: parseAsString.withDefault(""),
    sentiment: parseAsString.withDefault(""),
    halal: parseAsBoolean.withDefault(false),
  })

  const { data, isLoading } = useQuery<Signal[]>({
    queryKey: ["signals", params],
    queryFn: () =>
      fetchSignals({
        ticker: params.ticker || undefined,
        sentiment: params.sentiment || undefined,
        halal: params.halal || undefined,
      }),
  })

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Filter sidebar */}
      <div className="w-[220px] flex-shrink-0 border-r border-[#161616] bg-[#080808] overflow-y-auto p-4 space-y-5">
        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">
            Sentiment
          </div>
          {[
            { value: "", label: "All" },
            { value: "bullish", label: "Bullish" },
            { value: "bearish", label: "Bearish" },
            { value: "neutral", label: "Neutral" },
          ].map((s) => (
            <button
              key={s.value}
              onClick={() => setParams({ sentiment: s.value })}
              className={`flex items-center gap-2 w-full px-2 py-1.5 rounded text-xs mb-0.5 transition-colors ${
                params.sentiment === s.value
                  ? "bg-[#111] text-white"
                  : "text-[#4b5563] hover:text-[#94a3b8]"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">
            Compliance
          </div>
          <button
            onClick={() => setParams({ halal: !params.halal })}
            className={`flex items-center gap-2 w-full px-2 py-1.5 rounded text-xs transition-colors ${
              params.halal
                ? "bg-[#041008] text-[#22c55e]"
                : "text-[#4b5563] hover:text-[#94a3b8]"
            }`}
          >
            <span>☽</span> Halal only
          </button>
        </div>

        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">
            Ticker
          </div>
          <input
            type="text"
            placeholder="e.g. NVDA"
            value={params.ticker}
            onChange={(e) => setParams({ ticker: e.target.value.toUpperCase() })}
            className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-2 py-1.5 text-xs text-white placeholder-[#2d2d2d] focus:outline-none focus:border-[#2a2a2a]"
          />
        </div>
      </div>

      {/* Feed */}
      <div className="flex-1 overflow-y-auto">
        <div className="border-b border-[#111] px-4 py-2.5 bg-[#050505] flex items-center gap-3">
          <span className="text-xs text-[#4b5563]">
            {isLoading ? "Loading..." : `${data?.length ?? 0} signals`}
          </span>
          <span className="text-[#1c1c1c] text-xs">·</span>
          <span className="text-xs text-[#2d2d2d]">Sorted by confidence ↓</span>
          {(params.ticker || params.sentiment || params.halal) && (
            <button
              onClick={() => setParams({ ticker: "", sentiment: "", halal: false })}
              className="ml-auto text-[10px] text-[#374151] hover:text-[#94a3b8] transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>

        {isLoading && (
          <div className="p-8 text-center text-[#2d2d2d] text-xs">Loading signals...</div>
        )}
        {!isLoading && data?.length === 0 && (
          <div className="p-8 text-center text-[#2d2d2d] text-xs">
            No signals found — run a scrape cycle or adjust filters
          </div>
        )}
        {data?.map((s) => <SignalCard key={s.id} signal={s} />)}
      </div>
    </div>
  )
}
```

- [ ] Commit:
```bash
cd "C:/Users/makhs/Desktop/Projects/Argus" && git add web/app/\(app\)/intelligence/ && git commit -m "feat: intelligence feed with filters and signal cards"
```

---

## Task 4: AI Chat page with Vercel AI SDK

**Files:**
- Create: `web/app/api/chat/route.ts`
- Modify: `web/app/(app)/chat/page.tsx`

- [ ] Create `web/app/api/chat/route.ts`:
```typescript
import { anthropic } from "@ai-sdk/anthropic"
import { streamText } from "ai"

export const maxDuration = 60

const SYSTEM = `You are Argus Intelligence — an AI investment analyst backed by real-time data scraped from Reddit investment communities, SEC EDGAR filings, Stocktwits, Seeking Alpha, and 20+ financial sources. 

Your role: provide actionable, sourced investment intelligence. Every claim must reference its source. When you don't have specific scraped data, say so clearly and use your general financial knowledge.

Key behaviors:
- Always cite sources when making claims (e.g. "r/SecurityAnalysis · u/deepwater_val · 2,841 upvotes")
- For Shariah compliance questions, reference Zoya API / DJIMI / MSCI Islamic Index
- For directional calls, provide a confidence level and timeframe
- Be direct — this is for real investment decisions, not education
- Flag if something is speculation vs confirmed (SEC filing, earnings call, etc.)
- Format responses clearly with sections when appropriate`

export async function POST(req: Request) {
  const { messages, userProfile } = await req.json()

  const systemWithProfile = userProfile
    ? `${SYSTEM}\n\nUser profile: Budget $${userProfile.budget ?? "unknown"}, Risk tolerance: ${userProfile.risk_tolerance ?? "moderate"}, Goal: ${userProfile.investing_goal ?? "not set"}, Halal filter: ${userProfile.halal_filter ? "ACTIVE — only recommend Shariah-compliant investments" : "off"}.`
    : SYSTEM

  const result = streamText({
    model: anthropic("claude-opus-4-8"),
    system: systemWithProfile,
    messages,
  })

  return result.toDataStreamResponse()
}
```

- [ ] Replace `web/app/(app)/chat/page.tsx`:
```tsx
"use client"
import { useChat } from "ai/react"
import { useRef, useEffect } from "react"

const SUGGESTED = [
  "What should I invest in this week?",
  "Best halal picks right now ☽",
  "What did WSB say about NVDA recently?",
  "Summarize today's high-confidence signals",
  "What's the bearish case for TSLA?",
]

export default function ChatPage() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } =
    useChat({ api: "/api/chat" })
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="flex-1 flex flex-col">
        {/* Context bar */}
        <div className="flex items-center gap-3 px-6 py-2.5 border-b border-[#111] bg-[#050505] text-[10px] text-[#374151] flex-shrink-0">
          <span>Argus Intelligence · Claude Opus 4.8</span>
          <span className="text-[#1c1c1c]">·</span>
          <span className="bg-[#080808] border border-[#161616] rounded px-1.5 py-0.5 text-[#4b5563]">
            Live database
          </span>
          <span className="bg-[#041008] border border-[#0a2010] rounded px-1.5 py-0.5 text-[#22c55e]">
            ☽ Halal filter ready
          </span>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center pb-20">
              <div className="text-4xl font-bold tracking-[0.1em] uppercase text-[#111] mb-2">
                ARGUS
              </div>
              <div className="text-xs text-[#2d2d2d] mb-8">
                Ask about any stock, sector, or market trend
              </div>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {SUGGESTED.map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      handleInputChange({
                        target: { value: s },
                      } as React.ChangeEvent<HTMLInputElement>)
                    }}
                    className="text-[11px] bg-[#080808] border border-[#161616] rounded-md px-3 py-1.5 text-[#374151] hover:text-[#94a3b8] hover:border-[#2a2a2a] transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {m.role === "assistant" && (
                <div className="mr-2 mt-1 text-[10px] text-[#2d2d2d] flex-shrink-0 pt-1">
                  <span>◉</span>
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-lg px-4 py-3 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-[#0f0820] border border-[#1e1040] text-[#c4b5fd] rounded-br-sm"
                    : "bg-[#080808] border border-[#141414] text-[#9ca3af] rounded-bl-sm"
                }`}
              >
                {m.role === "assistant" && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#e2e8f0]" />
                    <span className="text-[9px] text-[#374151] tracking-[0.1em] uppercase">
                      Argus Intelligence
                    </span>
                  </div>
                )}
                <div className="whitespace-pre-wrap text-xs">{m.content}</div>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-[#080808] border border-[#141414] rounded-lg px-4 py-3">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="w-1 h-1 rounded-full bg-[#374151] animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-6 pb-6 flex-shrink-0">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              value={input}
              onChange={handleInputChange}
              placeholder="Ask anything — 'Best halal picks this week ☽', 'What did WSB say about NVDA?'..."
              className="flex-1 bg-[#0d0d0d] border border-[#1a1a1a] rounded-lg px-4 py-3 text-sm text-white placeholder-[#374151] focus:outline-none focus:border-[#2a2a2a] transition-colors"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="bg-[#111] border border-[#2a2a2a] text-[#e2e8f0] text-sm px-4 py-3 rounded-lg hover:bg-[#161616] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              Send →
            </button>
          </form>
        </div>
      </div>

      {/* Right context panel */}
      <div className="w-[240px] flex-shrink-0 border-l border-[#161616] bg-[#080808] p-4 space-y-4 overflow-y-auto">
        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">
            Your Profile
          </div>
          <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3 space-y-2">
            {[
              ["Budget", "$25,000"],
              ["Risk", "Moderate"],
              ["Goal", "Long-term"],
              ["Halal", "Active ☽"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-[#374151]">{k}</span>
                <span className={k === "Halal" ? "text-[#22c55e] font-semibold" : "text-[#9ca3af] font-semibold"}>
                  {v}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">
            Suggested
          </div>
          <div className="space-y-1">
            {SUGGESTED.map((s) => (
              <button
                key={s}
                onClick={() =>
                  handleInputChange({
                    target: { value: s },
                  } as React.ChangeEvent<HTMLInputElement>)
                }
                className="block w-full text-left text-[10px] text-[#374151] hover:text-[#94a3b8] py-1 transition-colors truncate"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
```

- [ ] Commit:
```bash
cd "C:/Users/makhs/Desktop/Projects/Argus" && git add web/app/api/ web/app/\(app\)/chat/ && git commit -m "feat: ai chat with claude opus streaming and user profile context"
```

---

## Task 5: Stock Deep Dive page

**Files:**
- Create: `web/components/price-chart.tsx`
- Modify: `web/app/(app)/stocks/[ticker]/page.tsx`

- [ ] Create `web/components/price-chart.tsx`:
```tsx
"use client"
import { useEffect, useRef } from "react"
import {
  createChart,
  ColorType,
  LineStyle,
} from "lightweight-charts"

interface PriceChartProps {
  ticker: string
}

export function PriceChart({ ticker }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#050505" },
        textColor: "#4b5563",
      },
      grid: {
        vertLines: { color: "#0d0d0d" },
        horzLines: { color: "#0d0d0d" },
      },
      crosshair: {
        vertLine: { color: "#2a2a2a" },
        horzLine: { color: "#2a2a2a" },
      },
      rightPriceScale: { borderColor: "#161616" },
      timeScale: { borderColor: "#161616" },
      width: containerRef.current.clientWidth,
      height: 200,
    })

    const lineSeries = chart.addLineSeries({
      color: "#22c55e",
      lineWidth: 1,
      lastValueVisible: true,
      priceLineVisible: false,
    })

    // Placeholder data until Polygon.io is wired in
    const now = Math.floor(Date.now() / 1000)
    const day = 86400
    lineSeries.setData(
      Array.from({ length: 30 }, (_, i) => ({
        time: (now - (29 - i) * day) as any,
        value: 100 + Math.sin(i * 0.4) * 10 + i * 0.5,
      }))
    )

    chart.timeScale().fitContent()

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth })
      }
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
    }
  }, [ticker])

  return <div ref={containerRef} className="w-full" />
}
```

- [ ] Replace `web/app/(app)/stocks/[ticker]/page.tsx`:
```tsx
import { fetchRecommendationByTicker, fetchSignals } from "@/lib/api"
import { PriceChart } from "@/components/price-chart"
import { SignalCard } from "@/components/ui/signal-card"
import { TickerBadge } from "@/components/ui/ticker-badge"
import { SentimentBar } from "@/components/ui/sentiment-bar"

interface Props {
  params: Promise<{ ticker: string }>
}

export default async function StockPage({ params }: Props) {
  const { ticker } = await params
  const upper = ticker.toUpperCase()

  const [rec, signals] = await Promise.all([
    fetchRecommendationByTicker(upper),
    fetchSignals({ ticker: upper }),
  ])

  const topSignals = signals.slice(0, 5)

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="font-mono text-3xl font-bold text-white tracking-wide">
                {upper}
              </span>
              {rec?.halal_compliant && (
                <span className="text-[#22c55e] text-lg" title="Shariah Compliant">
                  ☽
                </span>
              )}
              {rec?.direction && (
                <span
                  className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                    rec.direction === "buy"
                      ? "bg-[#041008] text-[#22c55e] border-[#0a2010]"
                      : "bg-[#140305] text-[#ef4444] border-[#280510]"
                  }`}
                >
                  {rec.direction === "buy" ? "BUY SIGNAL" : "AVOID"}
                </span>
              )}
            </div>
            {rec?.company_name && (
              <div className="text-sm text-[#4b5563]">{rec.company_name}</div>
            )}
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold font-mono text-white">—</div>
            <div className="text-xs text-[#4b5563]">
              Price data requires Polygon.io key
            </div>
          </div>
        </div>

        {/* Chart */}
        <div className="bg-[#080808] border border-[#161616] rounded-lg overflow-hidden">
          <div className="px-4 py-2 border-b border-[#111] text-[10px] text-[#2d2d2d] tracking-[0.1em] uppercase">
            {upper} · 30 day · Signal overlays
          </div>
          <PriceChart ticker={upper} />
        </div>

        {/* Claude analysis */}
        {rec?.ai_analysis && (
          <div className="bg-[#080808] border border-[#161616] rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="text-[10px] text-[#e2e8f0] font-bold tracking-[0.08em] uppercase">
                Argus Intelligence — Claude Opus 4.8
              </div>
              <div className="text-[9px] bg-[#111] border border-[#1c1c1c] rounded px-1.5 py-0.5 text-[#2d2d2d]">
                claude-opus-4-8
              </div>
            </div>
            <div className="text-xs text-[#9ca3af] leading-relaxed">
              {rec.ai_analysis}
            </div>
            {(rec.price_target_base || rec.price_target_bull || rec.price_target_bear) && (
              <div className="grid grid-cols-3 gap-3 mt-4">
                {[
                  { label: "Base target", val: rec.price_target_base },
                  { label: "Bull case", val: rec.price_target_bull },
                  { label: "Bear case", val: rec.price_target_bear },
                ].map(({ label, val }) => val != null && (
                  <div key={label} className="bg-[#0d0d0d] border border-[#161616] rounded-md p-3">
                    <div className="text-[9px] text-[#374151] uppercase tracking-[0.08em] mb-1">{label}</div>
                    <div className="text-sm font-bold font-mono text-[#22c55e]">
                      ${val.toFixed(2)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Key signals */}
        {topSignals.length > 0 && (
          <div className="bg-[#080808] border border-[#161616] rounded-lg overflow-hidden">
            <div className="px-4 py-2.5 border-b border-[#111] text-[10px] text-[#2d2d2d] tracking-[0.1em] uppercase">
              Key Signals — Top Source Excerpts
            </div>
            {topSignals.map((s) => <SignalCard key={s.id} signal={s} />)}
          </div>
        )}
      </div>

      {/* Right panel */}
      {rec && (
        <div className="w-[260px] flex-shrink-0 border-l border-[#161616] bg-[#080808] p-4 space-y-4 overflow-y-auto">
          <div>
            <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">
              Sentiment
            </div>
            <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3 space-y-2">
              {[
                { label: "Bullish", pct: rec.bull_pct, color: "#22c55e" },
                { label: "Neutral", pct: rec.neutral_pct, color: "#f59e0b" },
                { label: "Bearish", pct: rec.bear_pct, color: "#ef4444" },
              ].map(({ label, pct, color }) => (
                <div key={label} className="flex items-center gap-2 text-xs">
                  <span className="w-12 text-[#374151]">{label}</span>
                  <div className="flex-1 h-[3px] bg-[#161616] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${pct}%`, background: color }}
                    />
                  </div>
                  <span className="w-8 text-right font-bold font-mono" style={{ color }}>
                    {Math.round(pct)}%
                  </span>
                </div>
              ))}
              <div className="text-[10px] text-[#1c1c1c] pt-1 border-t border-[#0d0d0d]">
                {rec.signal_count.toLocaleString()} signals · {rec.source_count} sources
              </div>
            </div>
          </div>

          {rec.halal_compliant != null && (
            <div>
              <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">
                Halal Compliance
              </div>
              <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3">
                <div
                  className={`text-sm font-bold mb-2 ${
                    rec.halal_compliant ? "text-[#22c55e]" : "text-[#ef4444]"
                  }`}
                >
                  {rec.halal_compliant ? "☽ Shariah Compliant" : "✗ Not Compliant"}
                </div>
                <div className="text-[10px] text-[#374151]">
                  Source: Zoya API · DJIMI
                </div>
              </div>
            </div>
          )}

          <div>
            <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">
              Confidence
            </div>
            <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3">
              <div
                className="text-2xl font-bold font-mono mb-2"
                style={{
                  color:
                    rec.confidence >= 70
                      ? "#22c55e"
                      : rec.confidence >= 50
                      ? "#f59e0b"
                      : "#ef4444",
                }}
              >
                {rec.confidence}
                <span className="text-xs text-[#2d2d2d] font-normal">/100</span>
              </div>
              <div className="h-[3px] bg-[#161616] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${rec.confidence}%`,
                    background:
                      rec.confidence >= 70
                        ? "#22c55e"
                        : rec.confidence >= 50
                        ? "#f59e0b"
                        : "#ef4444",
                  }}
                />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] Commit:
```bash
cd "C:/Users/makhs/Desktop/Projects/Argus" && git add web/ && git commit -m "feat: stock deep dive with tradingview chart, claude analysis, signals"
```

---

## Task 6: Profile page and verify full build

**Files:**
- Modify: `web/app/(app)/profile/page.tsx`

- [ ] Replace `web/app/(app)/profile/page.tsx`:
```tsx
"use client"
import { useState } from "react"

type Goal = "retirement" | "short_term" | "passive_income" | "speculative"
type Risk = "conservative" | "moderate" | "aggressive"

const GOALS: { value: Goal; label: string; desc: string }[] = [
  { value: "retirement", label: "Long-term Retirement", desc: "10+ year horizon, wealth building" },
  { value: "short_term", label: "Short-term Trading", desc: "Days to months, active" },
  { value: "passive_income", label: "Passive Income", desc: "Dividends, REITs, steady yield" },
  { value: "speculative", label: "Speculative", desc: "High risk, high reward" },
]

const RISKS: { value: Risk; label: string; color: string }[] = [
  { value: "conservative", label: "Conservative", color: "text-[#22c55e]" },
  { value: "moderate", label: "Moderate", color: "text-[#f59e0b]" },
  { value: "aggressive", label: "Aggressive", color: "text-[#ef4444]" },
]

export default function ProfilePage() {
  const [budget, setBudget] = useState("25000")
  const [goal, setGoal] = useState<Goal>("retirement")
  const [risk, setRisk] = useState<Risk>("moderate")
  const [halal, setHalal] = useState(false)
  const [saved, setSaved] = useState(false)

  function handleSave() {
    // Persist to localStorage for now; API integration in Phase 3
    localStorage.setItem(
      "argus_profile",
      JSON.stringify({ budget, goal, risk, halal })
    )
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-white tracking-wide">
          Profile & Goals
        </h1>
        <p className="text-xs text-[#4b5563] mt-1">
          These preferences personalize every recommendation and AI chat response.
        </p>
      </div>

      {/* Budget */}
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4 space-y-3">
        <div className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase">
          Investable Budget
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[#4b5563] text-sm">$</span>
          <input
            type="number"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            className="flex-1 bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#2a2a2a]"
            min="0"
          />
        </div>
      </div>

      {/* Goal */}
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4 space-y-3">
        <div className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase">
          Investing Goal
        </div>
        <div className="grid grid-cols-2 gap-2">
          {GOALS.map((g) => (
            <button
              key={g.value}
              onClick={() => setGoal(g.value)}
              className={`text-left p-3 rounded-md border text-xs transition-colors ${
                goal === g.value
                  ? "bg-[#111] border-[#2a2a2a] text-white"
                  : "border-[#161616] text-[#4b5563] hover:text-[#94a3b8] hover:border-[#1c1c1c]"
              }`}
            >
              <div className="font-semibold mb-0.5">{g.label}</div>
              <div className="text-[10px] opacity-60">{g.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Risk */}
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4 space-y-3">
        <div className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase">
          Risk Tolerance
        </div>
        <div className="flex gap-2">
          {RISKS.map((r) => (
            <button
              key={r.value}
              onClick={() => setRisk(r.value)}
              className={`flex-1 py-2 rounded-md border text-xs font-semibold transition-colors ${
                risk === r.value
                  ? `bg-[#111] border-[#2a2a2a] ${r.color}`
                  : "border-[#161616] text-[#4b5563] hover:text-[#94a3b8]"
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Halal */}
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-white flex items-center gap-2">
              <span className="text-[#22c55e]">☽</span> Shariah Compliance Filter
            </div>
            <div className="text-[11px] text-[#4b5563] mt-1">
              Only show Zoya/DJIMI-verified halal investments across all pages
            </div>
          </div>
          <button
            onClick={() => setHalal(!halal)}
            className={`w-10 h-5 rounded-full transition-colors relative ${
              halal ? "bg-[#22c55e]" : "bg-[#161616]"
            }`}
          >
            <div
              className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                halal ? "translate-x-5" : "translate-x-0.5"
              }`}
            />
          </button>
        </div>
      </div>

      {/* Save */}
      <button
        onClick={handleSave}
        className="w-full py-3 rounded-lg border text-sm font-semibold transition-colors bg-[#111] border-[#2a2a2a] text-[#e2e8f0] hover:bg-[#161616]"
      >
        {saved ? "✓ Saved" : "Save Profile"}
      </button>
    </div>
  )
}
```

- [ ] Run full build and verify:
```bash
cd "C:/Users/makhs/Desktop/Projects/Argus/web" && npm run build 2>&1 | tail -20
```

- [ ] Commit and push:
```bash
cd "C:/Users/makhs/Desktop/Projects/Argus" && git add web/ && git commit -m "feat: profile page with goal, risk, budget, halal filter" && git push origin main
```
