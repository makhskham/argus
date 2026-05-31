"use client"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { useRef, useEffect, useState } from "react"

const SUGGESTED = [
  "What should I invest in this week?",
  "Best halal picks right now ☽",
  "What did WSB say about NVDA recently?",
  "Summarize today's high-confidence signals",
  "What is the bearish case for TSLA?",
]

export default function ChatPage() {
  const { messages, sendMessage, status } = useChat({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  })
  const [input, setInput] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)
  const isLoading = status === "submitted" || status === "streaming"

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || isLoading) return
    sendMessage({ text: input })
    setInput("")
  }

  function handleSuggest(s: string) {
    setInput(s)
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="flex-1 flex flex-col">
        <div className="flex items-center gap-3 px-6 py-2.5 border-b border-[#111] bg-[#050505] text-[10px] text-[#374151] flex-shrink-0">
          <span>Argus Intelligence · Claude Opus 4.5</span>
          <span className="text-[#1c1c1c]">·</span>
          <span className="bg-[#080808] border border-[#161616] rounded px-1.5 py-0.5 text-[#4b5563]">Live database</span>
          <span className="bg-[#041008] border border-[#0a2010] rounded px-1.5 py-0.5 text-[#22c55e]">☽ Halal filter ready</span>
        </div>
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center pb-20">
              <div className="text-4xl font-bold tracking-[0.1em] uppercase text-[#111] mb-2">ARGUS</div>
              <div className="text-xs text-[#2d2d2d] mb-8">Ask about any stock, sector, or market trend</div>
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {SUGGESTED.map((s) => (
                  <button key={s} onClick={() => handleSuggest(s)}
                    className="text-[11px] bg-[#080808] border border-[#161616] rounded-md px-3 py-1.5 text-[#374151] hover:text-[#94a3b8] hover:border-[#2a2a2a] transition-colors">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              {m.role === "assistant" && <div className="mr-2 mt-1 text-[10px] text-[#2d2d2d] flex-shrink-0 pt-1">◉</div>}
              <div className={`max-w-[80%] rounded-lg px-4 py-3 text-sm leading-relaxed ${m.role === "user" ? "bg-[#0f0820] border border-[#1e1040] text-[#c4b5fd] rounded-br-sm" : "bg-[#080808] border border-[#141414] text-[#9ca3af] rounded-bl-sm"}`}>
                {m.role === "assistant" && (
                  <div className="flex items-center gap-1.5 mb-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-[#e2e8f0]" />
                    <span className="text-[9px] text-[#374151] tracking-[0.1em] uppercase">Argus Intelligence</span>
                  </div>
                )}
                <div className="whitespace-pre-wrap text-xs">
                  {m.parts.map((part, i) =>
                    part.type === "text" ? <span key={i}>{part.text}</span> : null
                  )}
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-[#080808] border border-[#141414] rounded-lg px-4 py-3">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="w-1 h-1 rounded-full bg-[#374151] animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <div className="px-6 pb-6 flex-shrink-0">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input value={input} onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything — 'Best halal picks this week ☽', 'What did WSB say about NVDA?'..."
              className="flex-1 bg-[#0d0d0d] border border-[#1a1a1a] rounded-lg px-4 py-3 text-sm text-white placeholder-[#374151] focus:outline-none focus:border-[#2a2a2a] transition-colors" />
            <button type="submit" disabled={isLoading || !input.trim()}
              className="bg-[#111] border border-[#2a2a2a] text-[#e2e8f0] text-sm px-4 py-3 rounded-lg hover:bg-[#161616] disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
              Send →
            </button>
          </form>
        </div>
      </div>
      <div className="w-[240px] flex-shrink-0 border-l border-[#161616] bg-[#080808] p-4 space-y-4 overflow-y-auto">
        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">Your Profile</div>
          <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3 space-y-2">
            {([["Budget", "$25,000"], ["Risk", "Moderate"], ["Goal", "Long-term"], ["Halal", "Active ☽"]] as [string, string][]).map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-[#374151]">{k}</span>
                <span className={k === "Halal" ? "text-[#22c55e] font-semibold" : "text-[#9ca3af] font-semibold"}>{v}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="text-[9px] text-[#1c1c1c] tracking-[0.12em] uppercase mb-2">Suggested</div>
          <div className="space-y-1">
            {SUGGESTED.map((s) => (
              <button key={s} onClick={() => handleSuggest(s)}
                className="block w-full text-left text-[10px] text-[#374151] hover:text-[#94a3b8] py-1 transition-colors truncate">
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
