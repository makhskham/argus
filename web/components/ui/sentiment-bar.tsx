interface SentimentBarProps {
  bull: number
  neutral: number
  bear: number
}

export function SentimentBar({ bull, neutral, bear }: SentimentBarProps) {
  return (
    <div className="flex items-center gap-1 text-[11px]">
      <span className="text-[#22c55e] font-medium">{Math.round(bull)}%</span>
      <span className="text-[#1c1c1c]">·</span>
      <span className="text-[#f59e0b]">{Math.round(neutral)}%</span>
      <span className="text-[#1c1c1c]">·</span>
      <span className="text-[#ef4444]">{Math.round(bear)}%</span>
    </div>
  )
}
