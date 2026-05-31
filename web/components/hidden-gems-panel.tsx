"use client"
import { useQuery } from "@tanstack/react-query"
import { fetchEmergingTickers, EmergingTicker } from "@/lib/api"
import { TickerBadge } from "./ui/ticker-badge"

interface Props {
  halal: boolean
}

function GemRow({ gem }: { gem: EmergingTicker }) {
  const velocityStr =
    gem.momentum_score != null ? `${gem.momentum_score.toFixed(1)}x` : "—"

  return (
    <a
      href={`/stocks/${gem.ticker}`}
      className="block px-4 py-3 border-b border-[#0a0a0a] hover:bg-[#050505] transition-colors"
    >
      <div className="flex items-center gap-2 mb-1.5">
        <TickerBadge ticker={gem.ticker} halalCompliant={gem.halal_compliant} />
        {gem.market_cap_tier && gem.market_cap_tier !== "unknown" && (
          <span className="text-[9px] bg-[#111] border border-[#1c1c1c] rounded px-1.5 py-0.5 text-[#4b5563] uppercase">
            {gem.market_cap_tier}
          </span>
        )}
        {gem.stock_price != null && (
          <span className="text-[10px] text-[#4b5563] font-mono ml-auto">
            ${gem.stock_price.toFixed(2)}
          </span>
        )}
      </div>
      {gem.source_subreddit && (
        <div className="text-[9px] text-[#2d2d2d] mb-1">
          First seen: r/{gem.source_subreddit.replace("r/", "")}
        </div>
      )}
      {gem.first_mention_body && (
        <p className="text-[10px] text-[#374151] italic line-clamp-2 mb-1.5">
          &ldquo;{gem.first_mention_body.slice(0, 120)}&rdquo;
        </p>
      )}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <span className="text-[9px] text-[#2d2d2d]">Velocity</span>
          <span className="text-[10px] font-bold text-[#f59e0b] font-mono">
            {velocityStr}
          </span>
        </div>
        {gem.graduation_score > 0 && (
          <div className="flex items-center gap-1">
            <span className="text-[9px] text-[#2d2d2d]">Score</span>
            <span className="text-[10px] font-bold text-[#e2e8f0] font-mono">
              {Math.round(gem.graduation_score)}
            </span>
          </div>
        )}
        {gem.signal_count != null && (
          <span className="text-[9px] text-[#2d2d2d]">
            {gem.signal_count} mentions
          </span>
        )}
        <span className="text-[9px] bg-[#1a1208] text-[#d97706] rounded px-1 py-0.5 ml-auto">
          ↑ rising
        </span>
      </div>
    </a>
  )
}

export function HiddenGemsPanel({ halal }: Props) {
  const { data, isLoading } = useQuery<EmergingTicker[]>({
    queryKey: ["emerging", halal],
    queryFn: () => fetchEmergingTickers(halal),
    refetchInterval: 120_000,
  })

  return (
    <div className="bg-[#080808] border border-[#161616] rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#111]">
        <div className="flex items-center gap-2">
          <div className="text-[10px] font-bold text-[#4b5563] tracking-[0.1em] uppercase">
            Hidden Gems
          </div>
          <span className="text-[9px] bg-[#1a1208] text-[#d97706] rounded px-1.5 py-0.5">
            ↑ Rising fast
          </span>
        </div>
        <a
          href="/intelligence?sort=momentum"
          className="text-[10px] text-[#2d2d2d] hover:text-[#94a3b8] transition-colors"
        >
          View all →
        </a>
      </div>

      <div className="px-4 py-2 border-b border-[#0a0a0a] bg-[#050505]">
        <p className="text-[9px] text-[#2d2d2d] leading-relaxed">
          Obscure companies being discussed in niche forums before going mainstream.
          High velocity = mention count growing fast. These are pre-discovery picks.
        </p>
      </div>

      {isLoading && (
        <div className="px-4 py-6 text-center text-[#2d2d2d] text-xs">
          Scanning for emerging tickers...
        </div>
      )}
      {!isLoading && (!data || data.length === 0) && (
        <div className="px-4 py-6 text-center text-[#2d2d2d] text-xs">
          No emerging tickers detected yet.
          <br />
          <span className="text-[9px]">Run a scrape cycle to populate velocity data.</span>
        </div>
      )}
      {data?.slice(0, 8).map((gem) => <GemRow key={gem.ticker} gem={gem} />)}
    </div>
  )
}
