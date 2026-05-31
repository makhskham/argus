"use client"
import { parseAsBoolean, parseAsString, useQueryStates } from "nuqs"
import { StatCard } from "@/components/ui/stat-card"
import { RecommendationTable } from "@/components/recommendation-table"
import { BreakingSignalsPanel } from "@/components/breaking-signals-panel"

export function DashboardClient() {
  const [params, setParams] = useQueryStates({
    halal: parseAsBoolean.withDefault(false),
    tab: parseAsString.withDefault("all"),
  })

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <div className="flex items-center gap-4 px-6 py-3 border-b border-[#111] bg-black/80 backdrop-blur-sm flex-shrink-0">
        <div>
          <div className="text-sm font-bold text-white tracking-[0.04em]">Command Center</div>
          <div className="text-[10px] text-[#2d2d2d]">
            {params.halal ? "Shariah Compliant" : "All Markets"} · Last 7 days
          </div>
        </div>
        <div className="ml-auto flex items-center gap-3">
          <div className="flex bg-[#080808] border border-[#161616] rounded-md p-0.5">
            <button
              onClick={() => setParams({ tab: "all", halal: false })}
              className={`px-3 py-1.5 rounded text-xs transition-colors ${!params.halal ? "bg-[#111] text-white border border-[#2a2a2a]" : "text-[#4b5563] hover:text-[#94a3b8]"}`}
            >
              All Markets
            </button>
            <button
              onClick={() => setParams({ tab: "halal", halal: true })}
              className={`px-3 py-1.5 rounded text-xs transition-colors flex items-center gap-1 ${params.halal ? "bg-[#041008] text-[#22c55e] border border-[#0a2010]" : "text-[#4b5563] hover:text-[#94a3b8]"}`}
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
      <div className="flex-1 overflow-y-auto">
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-4 gap-3">
            <StatCard label="Market Sentiment" value="—" sub="Awaiting data" />
            <StatCard label="Posts Analyzed" value="—" sub="Run scraper first" />
            <StatCard label="High-Conf Signals" value="—" sub="Confidence > 80" />
            <StatCard label="Halal Picks" value="☽ —" sub="Shariah compliant" valueColor="text-[#22c55e]" />
          </div>
          <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 320px" }}>
            <div className="space-y-4">
              <RecommendationTable direction="buy" halal={params.halal} />
              <RecommendationTable direction="avoid" halal={params.halal} />
            </div>
            <div><BreakingSignalsPanel /></div>
          </div>
        </div>
      </div>
    </div>
  )
}
