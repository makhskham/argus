interface TickerBadgeProps {
  ticker: string
  halalCompliant?: boolean | null
}

export function TickerBadge({ ticker, halalCompliant }: TickerBadgeProps) {
  return (
    <span className="flex items-center gap-1">
      <span className="font-mono font-bold text-white tracking-wide">
        {ticker}
      </span>
      {halalCompliant && (
        <span
          className="text-[#22c55e] text-xs"
          title="Shariah Compliant — verified by Zoya / DJIMI"
        >
          ☽
        </span>
      )}
    </span>
  )
}
