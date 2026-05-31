"use client"
import { parseAsBoolean, parseAsString, useQueryStates } from "nuqs"
import { useQuery } from "@tanstack/react-query"
import { fetchSignals, Signal } from "@/lib/api"
import { SignalCard } from "@/components/ui/signal-card"

export function IntelligenceClient() {
  const [params, setParams] = useQueryStates({
    ticker: parseAsString.withDefault(""),
    sentiment: parseAsString.withDefault(""),
    halal: parseAsBoolean.withDefault(false),
  })
  const { data, isLoading } = useQuery<Signal[]>({
    queryKey: ["signals", params],
    queryFn: () => fetchSignals({
      ticker: params.ticker || undefined,
      sentiment: params.sentiment || undefined,
      halal: params.halal || undefined,
    }),
  })
  return (
    <div className="flex h-screen overflow-hidden">
      <div className="w-[220px] flex-shrink-0 border-r border-[#161616] bg-[#080808] overflow-y-auto p-4 space-y-5">
        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">Sentiment</div>
          {[{ value: "", label: "All" }, { value: "bullish", label: "Bullish" }, { value: "bearish", label: "Bearish" }, { value: "neutral", label: "Neutral" }].map((s) => (
            <button key={s.value} onClick={() => setParams({ sentiment: s.value })}
              className={`flex items-center gap-2 w-full px-2 py-1.5 rounded text-xs mb-0.5 transition-colors ${params.sentiment === s.value ? "bg-[#111] text-white" : "text-[#4b5563] hover:text-[#94a3b8]"}`}>
              {s.label}
            </button>
          ))}
        </div>
        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">Compliance</div>
          <button onClick={() => setParams({ halal: !params.halal })}
            className={`flex items-center gap-2 w-full px-2 py-1.5 rounded text-xs transition-colors ${params.halal ? "bg-[#041008] text-[#22c55e]" : "text-[#4b5563] hover:text-[#94a3b8]"}`}>
            <span>☽</span> Halal only
          </button>
        </div>
        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">Ticker</div>
          <input type="text" placeholder="e.g. NVDA" value={params.ticker}
            onChange={(e) => setParams({ ticker: e.target.value.toUpperCase() })}
            className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-2 py-1.5 text-xs text-white placeholder-[#2d2d2d] focus:outline-none focus:border-[#2a2a2a]" />
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="border-b border-[#111] px-4 py-2.5 bg-[#050505] flex items-center gap-3">
          <span className="text-xs text-[#4b5563]">{isLoading ? "Loading..." : `${data?.length ?? 0} signals`}</span>
          <span className="text-[#1c1c1c] text-xs">·</span>
          <span className="text-xs text-[#2d2d2d]">Sorted by confidence ↓</span>
          {(params.ticker || params.sentiment || params.halal) && (
            <button onClick={() => setParams({ ticker: "", sentiment: "", halal: false })}
              className="ml-auto text-[10px] text-[#374151] hover:text-[#94a3b8] transition-colors">
              Clear filters
            </button>
          )}
        </div>
        {isLoading && <div className="p-8 text-center text-[#2d2d2d] text-xs">Loading signals...</div>}
        {!isLoading && data?.length === 0 && <div className="p-8 text-center text-[#2d2d2d] text-xs">No signals found — run a scrape cycle or adjust filters</div>}
        {data?.map((s) => <SignalCard key={s.id} signal={s} />)}
      </div>
    </div>
  )
}
