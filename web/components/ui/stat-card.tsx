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
