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
  const [perStockBudget, setPerStockBudget] = useState("500")
  const [goal, setGoal] = useState<Goal>("retirement")
  const [risk, setRisk] = useState<Risk>("moderate")
  const [halal, setHalal] = useState(false)
  const [saved, setSaved] = useState(false)

  function handleSave() {
    localStorage.setItem("argus_profile", JSON.stringify({ budget, per_stock_budget: parseFloat(perStockBudget) || null, goal, risk, halal }))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-lg font-bold text-white tracking-wide">Profile &amp; Goals</h1>
        <p className="text-xs text-[#4b5563] mt-1">These preferences personalize every recommendation and AI chat response.</p>
      </div>
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4 space-y-3">
        <div className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase">Investable Budget</div>
        <div className="flex items-center gap-2">
          <span className="text-[#4b5563] text-sm">$</span>
          <input type="number" value={budget} onChange={(e) => setBudget(e.target.value)}
            className="flex-1 bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#2a2a2a]" min="0" />
        </div>
      </div>
      {/* Per-stock budget */}
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4 space-y-3">
        <div className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase">
          Max Per Single Stock
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[#4b5563] text-sm">$</span>
          <input
            type="number"
            value={perStockBudget}
            onChange={(e) => setPerStockBudget(e.target.value)}
            placeholder="e.g. 500"
            className="flex-1 bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-sm text-white font-mono focus:outline-none focus:border-[#2a2a2a]"
            min="0"
          />
        </div>
        <p className="text-[10px] text-[#374151]">
          Argus will only recommend stocks at or below this price per share.
          Lower values surface niche and micro-cap opportunities.
        </p>
      </div>
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4 space-y-3">
        <div className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase">Investing Goal</div>
        <div className="grid grid-cols-2 gap-2">
          {GOALS.map((g) => (
            <button key={g.value} onClick={() => setGoal(g.value)}
              className={`text-left p-3 rounded-md border text-xs transition-colors ${goal === g.value ? "bg-[#111] border-[#2a2a2a] text-white" : "border-[#161616] text-[#4b5563] hover:text-[#94a3b8] hover:border-[#1c1c1c]"}`}>
              <div className="font-semibold mb-0.5">{g.label}</div>
              <div className="text-[10px] opacity-60">{g.desc}</div>
            </button>
          ))}
        </div>
      </div>
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4 space-y-3">
        <div className="text-[10px] text-[#2d2d2d] tracking-[0.12em] uppercase">Risk Tolerance</div>
        <div className="flex gap-2">
          {RISKS.map((r) => (
            <button key={r.value} onClick={() => setRisk(r.value)}
              className={`flex-1 py-2 rounded-md border text-xs font-semibold transition-colors ${risk === r.value ? `bg-[#111] border-[#2a2a2a] ${r.color}` : "border-[#161616] text-[#4b5563] hover:text-[#94a3b8]"}`}>
              {r.label}
            </button>
          ))}
        </div>
      </div>
      <div className="bg-[#080808] border border-[#161616] rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-white flex items-center gap-2"><span className="text-[#22c55e]">☽</span> Shariah Compliance Filter</div>
            <div className="text-[11px] text-[#4b5563] mt-1">Only show Zoya/DJIMI-verified halal investments across all pages</div>
          </div>
          <button onClick={() => setHalal(!halal)} className={`w-10 h-5 rounded-full transition-colors relative ${halal ? "bg-[#22c55e]" : "bg-[#161616]"}`}>
            <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${halal ? "translate-x-5" : "translate-x-0.5"}`} />
          </button>
        </div>
      </div>
      <button onClick={handleSave} className="w-full py-3 rounded-lg border text-sm font-semibold transition-colors bg-[#111] border-[#2a2a2a] text-[#e2e8f0] hover:bg-[#161616]">
        {saved ? "✓ Saved" : "Save Profile"}
      </button>
    </div>
  )
}
