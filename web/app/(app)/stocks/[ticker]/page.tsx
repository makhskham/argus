import { fetchRecommendationByTicker, fetchSignals } from "@/lib/api"
import { PriceChart } from "@/components/price-chart"
import { SignalCard } from "@/components/ui/signal-card"

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
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="font-mono text-3xl font-bold text-white tracking-wide">{upper}</span>
              {rec?.halal_compliant && <span className="text-[#22c55e] text-lg" title="Shariah Compliant">☽</span>}
              {rec?.direction && (
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${rec.direction === "buy" ? "bg-[#041008] text-[#22c55e] border-[#0a2010]" : "bg-[#140305] text-[#ef4444] border-[#280510]"}`}>
                  {rec.direction === "buy" ? "BUY SIGNAL" : "AVOID"}
                </span>
              )}
            </div>
            {rec?.company_name && <div className="text-sm text-[#4b5563]">{rec.company_name}</div>}
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold font-mono text-white">—</div>
            <div className="text-xs text-[#4b5563]">Price data requires Polygon.io key</div>
          </div>
        </div>
        <div className="bg-[#080808] border border-[#161616] rounded-lg overflow-hidden">
          <div className="px-4 py-2 border-b border-[#111] text-[10px] text-[#2d2d2d] tracking-[0.1em] uppercase">
            {upper} · 30 day · Signal overlays
          </div>
          <PriceChart ticker={upper} />
        </div>
        {rec?.ai_analysis && (
          <div className="bg-[#080808] border border-[#161616] rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <div className="text-[10px] text-[#e2e8f0] font-bold tracking-[0.08em] uppercase">Argus Intelligence — Claude Opus 4.5</div>
              <div className="text-[9px] bg-[#111] border border-[#1c1c1c] rounded px-1.5 py-0.5 text-[#2d2d2d]">claude-opus-4-5</div>
            </div>
            <div className="text-xs text-[#9ca3af] leading-relaxed">{rec.ai_analysis}</div>
            {(rec.price_target_base || rec.price_target_bull || rec.price_target_bear) && (
              <div className="grid grid-cols-3 gap-3 mt-4">
                {(
                  [
                    ["Base target", rec.price_target_base],
                    ["Bull case", rec.price_target_bull],
                    ["Bear case", rec.price_target_bear],
                  ] as [string, number | null][]
                ).map(
                  ([label, val]) =>
                    val != null && (
                      <div key={label} className="bg-[#0d0d0d] border border-[#161616] rounded-md p-3">
                        <div className="text-[9px] text-[#374151] uppercase tracking-[0.08em] mb-1">{label}</div>
                        <div className="text-sm font-bold font-mono text-[#22c55e]">${val.toFixed(2)}</div>
                      </div>
                    )
                )}
              </div>
            )}
          </div>
        )}
        {topSignals.length > 0 && (
          <div className="bg-[#080808] border border-[#161616] rounded-lg overflow-hidden">
            <div className="px-4 py-2.5 border-b border-[#111] text-[10px] text-[#2d2d2d] tracking-[0.1em] uppercase">Key Signals — Top Source Excerpts</div>
            {topSignals.map((s) => <SignalCard key={s.id} signal={s} />)}
          </div>
        )}
      </div>
      {rec && (
        <div className="w-[260px] flex-shrink-0 border-l border-[#161616] bg-[#080808] p-4 space-y-4 overflow-y-auto">
          <div>
            <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">Sentiment</div>
            <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3 space-y-2">
              {(
                [
                  ["Bullish", rec.bull_pct, "#22c55e"],
                  ["Neutral", rec.neutral_pct, "#f59e0b"],
                  ["Bearish", rec.bear_pct, "#ef4444"],
                ] as [string, number, string][]
              ).map(([label, pct, color]) => (
                <div key={label} className="flex items-center gap-2 text-xs">
                  <span className="w-12 text-[#374151]">{label}</span>
                  <div className="flex-1 h-[3px] bg-[#161616] rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                  </div>
                  <span className="w-8 text-right font-bold font-mono" style={{ color }}>{Math.round(pct)}%</span>
                </div>
              ))}
              <div className="text-[10px] text-[#1c1c1c] pt-1 border-t border-[#0d0d0d]">
                {rec.signal_count.toLocaleString()} signals · {rec.source_count} sources
              </div>
            </div>
          </div>
          {rec.halal_compliant != null && (
            <div>
              <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">Halal Compliance</div>
              <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3">
                <div className={`text-sm font-bold mb-2 ${rec.halal_compliant ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
                  {rec.halal_compliant ? "☽ Shariah Compliant" : "✗ Not Compliant"}
                </div>
                <div className="text-[10px] text-[#374151]">Source: Zoya API · DJIMI</div>
              </div>
            </div>
          )}
          <div>
            <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">Confidence</div>
            <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3">
              <div
                className="text-2xl font-bold font-mono mb-2"
                style={{
                  color: rec.confidence >= 70 ? "#22c55e" : rec.confidence >= 50 ? "#f59e0b" : "#ef4444",
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
                    background: rec.confidence >= 70 ? "#22c55e" : rec.confidence >= 50 ? "#f59e0b" : "#ef4444",
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
