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
        <div className="text-[10px] font-bold text-[#4b5563] tracking-[0.1em] uppercase">Breaking Signals</div>
        <a href="/intelligence" className="text-[10px] text-[#2d2d2d] hover:text-[#94a3b8] transition-colors">View all →</a>
      </div>
      {top.length === 0
        ? <div className="px-4 py-6 text-center text-[#2d2d2d] text-xs">No signals yet</div>
        : top.map((s) => <SignalCard key={s.id} signal={s} compact />)
      }
    </div>
  )
}
