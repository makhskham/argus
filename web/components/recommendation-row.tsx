import Link from "next/link"
import { Recommendation } from "@/lib/api"
import { TickerBadge } from "./ui/ticker-badge"
import { SentimentBar } from "./ui/sentiment-bar"

interface Props {
  rec: Recommendation
  index: number
}

export function RecommendationRow({ rec, index }: Props) {
  const rank = index + 1
  const isBuy = rec.direction === "buy"
  const confColor =
    rec.confidence >= 70 ? "#22c55e" : rec.confidence >= 50 ? "#f59e0b" : "#ef4444"

  return (
    <Link
      href={`/stocks/${rec.ticker}`}
      className="grid items-center gap-2 px-4 py-2.5 border-b border-[#0a0a0a] hover:bg-[#0a0a0a] transition-colors cursor-pointer"
      style={{ gridTemplateColumns: "28px 1fr 110px 110px 90px 70px" }}
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
          {rec.is_emerging && (
            <span className="text-[8px] bg-[#1a1208] text-[#d97706] rounded px-1 py-0.5 flex-shrink-0">
              ↑ gem
            </span>
          )}
          {rec.market_cap_tier &&
            rec.market_cap_tier !== "unknown" &&
            (rec.market_cap_tier === "micro" || rec.market_cap_tier === "small") && (
              <span className="text-[8px] bg-[#111] border border-[#1c1c1c] rounded px-1 py-0.5 text-[#374151] flex-shrink-0 uppercase">
                {rec.market_cap_tier}
              </span>
            )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {rec.company_name && (
            <div className="text-[10px] text-[#2d2d2d] truncate">
              {rec.company_name}
            </div>
          )}
          {rec.stock_price != null && (
            <div className="text-[9px] text-[#1c1c1c] font-mono flex-shrink-0">
              ${rec.stock_price.toFixed(2)}
            </div>
          )}
        </div>
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

      <SentimentBar
        bull={rec.bull_pct}
        neutral={rec.neutral_pct}
        bear={rec.bear_pct}
      />

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
        {rec.momentum_score != null && rec.momentum_score > 2
          ? `${rec.momentum_score.toFixed(1)}x`
          : "—"}
      </div>
    </Link>
  )
}
