import { TrustBadge } from "./trust-badge"
import { TickerBadge } from "./ticker-badge"
import { Signal } from "@/lib/api"

const SENTIMENT_LABEL = {
  bullish: { text: "Bullish", className: "bg-[#041008] text-[#22c55e]" },
  bearish: { text: "Bearish", className: "bg-[#140305] text-[#ef4444]" },
  neutral: { text: "Neutral", className: "bg-[#120d00] text-[#f59e0b]" },
}

interface SignalCardProps {
  signal: Signal
  compact?: boolean
}

export function SignalCard({ signal, compact }: SignalCardProps) {
  const sentConf = signal.sentiment ? SENTIMENT_LABEL[signal.sentiment] : null
  const ago = signal.posted_at
    ? Math.round(
        (Date.now() - new Date(signal.posted_at).getTime()) / 3_600_000
      ) + "h ago"
    : ""

  return (
    <div className="px-4 py-3 border-b border-[#0d0d0d] hover:bg-[#050505] transition-colors">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {signal.tickers?.slice(0, 3).map((t) => (
          <TickerBadge
            key={t}
            ticker={t}
            halalCompliant={signal.halal_compliant}
          />
        ))}
        <span className="text-[10px] bg-[#111] border border-[#161616] rounded px-1.5 py-0.5 text-[#4b5563]">
          {signal.source}
        </span>
        {sentConf && (
          <span
            className={`text-[10px] rounded px-1.5 py-0.5 font-semibold ${sentConf.className}`}
          >
            {sentConf.text}
          </span>
        )}
        {signal.trust_tier && signal.trust_tier !== "unverified" && (
          <TrustBadge tier={signal.trust_tier} />
        )}
        <span className="text-[10px] text-[#1c1c1c] ml-auto">{ago}</span>
      </div>

      {!compact && (
        <p className="text-[12px] text-[#4b5563] leading-relaxed italic mb-2 line-clamp-3">
          {signal.key_quote || signal.body.slice(0, 240)}
        </p>
      )}

      <div className="flex items-center gap-3">
        {signal.confidence != null && (
          <div className="flex items-center gap-1.5">
            <div className="w-16 h-[3px] bg-[#161616] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${signal.confidence}%`,
                  background:
                    signal.confidence >= 70
                      ? "#22c55e"
                      : signal.confidence >= 50
                      ? "#f59e0b"
                      : "#ef4444",
                }}
              />
            </div>
            <span
              className={`text-[11px] font-bold font-mono ${
                signal.confidence >= 70
                  ? "text-[#22c55e]"
                  : signal.confidence >= 50
                  ? "text-[#f59e0b]"
                  : "text-[#ef4444]"
              }`}
            >
              {signal.confidence}
            </span>
          </div>
        )}
        {signal.upvotes > 0 && (
          <span className="text-[11px] text-[#2d2d2d]">
            ↑ {signal.upvotes.toLocaleString()}
          </span>
        )}
        {signal.is_niche_flagged && (
          <span className="text-[9px] bg-[#1a1208] text-[#d97706] rounded px-1.5 py-0.5">
            ★ niche insight
          </span>
        )}
        {signal.url && (
          <a
            href={signal.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[10px] text-[#1c1c1c] hover:text-[#94a3b8] ml-auto transition-colors"
          >
            View →
          </a>
        )}
      </div>
    </div>
  )
}
