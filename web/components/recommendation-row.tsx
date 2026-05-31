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
      <div className={`text-xs font-mono font-bold text-center ${rank <= 3 ? "text-[#e2e8f0]" : "text-[#1c1c1c]"}`}>
        {rank}
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <TickerBadge ticker={rec.ticker} halalCompliant={rec.halal_compliant} />
        </div>
        {rec.company_name && (
          <div className="text-[10px] text-[#2d2d2d] truncate mt-0.5">{rec.company_name}</div>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        <div className="flex-1 h-[3px] bg-[#161616] rounded-full overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${rec.confidence}%`, background: confColor }} />
        </div>
        <span className="text-xs font-bold font-mono w-6 text-right" style={{ color: confColor }}>
          {rec.confidence}
        </span>
      </div>
      <SentimentBar bull={rec.bull_pct} neutral={rec.neutral_pct} bear={rec.bear_pct} />
      <div className="text-[10px] text-[#2d2d2d] text-right">
        {rec.signal_count.toLocaleString()}<br />
        <span className="text-[#1c1c1c]">{rec.source_count} src</span>
      </div>
      <div className={`text-xs font-bold font-mono text-right ${isBuy ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
        —
      </div>
    </Link>
  )
}
