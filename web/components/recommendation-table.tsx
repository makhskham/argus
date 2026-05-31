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
        <div>#</div><div>Ticker</div><div>Confidence</div>
        <div>Sentiment</div><div className="text-right">Sources</div><div className="text-right">Momentum</div>
      </div>
      {isLoading && <div className="px-4 py-8 text-center text-[#2d2d2d] text-xs">Loading...</div>}
      {error && <div className="px-4 py-8 text-center text-[#4b5563] text-xs">API not reachable — start the Go backend</div>}
      {data?.map((rec, i) => <RecommendationRow key={rec.id} rec={rec} index={i} />)}
      {data?.length === 0 && !isLoading && (
        <div className="px-4 py-8 text-center text-[#2d2d2d] text-xs">No data yet — run a scrape cycle first</div>
      )}
    </div>
  )
}
