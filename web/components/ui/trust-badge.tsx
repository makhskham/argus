const TIERS = {
  authority: {
    label: "AUTHORITY",
    className: "bg-[#161616] text-[#e2e8f0] border border-[#2a2a2a]",
  },
  trusted: {
    label: "TRUSTED",
    className: "bg-[#041008] text-[#22c55e] border border-[#0a2010]",
  },
  recognized: {
    label: "RECOGNIZED",
    className: "bg-[#120d00] text-[#f59e0b] border border-[#2a1e00]",
  },
  unverified: null,
}

interface TrustBadgeProps {
  tier: string | null | undefined
}

export function TrustBadge({ tier }: TrustBadgeProps) {
  if (!tier || tier === "unverified") return null
  const config = TIERS[tier as keyof typeof TIERS]
  if (!config) return null
  return (
    <span
      className={`text-[9px] font-bold tracking-[0.06em] px-1.5 py-0.5 rounded ${config.className}`}
    >
      {config.label}
    </span>
  )
}
