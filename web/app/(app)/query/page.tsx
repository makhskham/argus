"use client"
import { useState, useRef } from "react"

type ResultType = "posts" | "comments"
type SortType = "score" | "created_utc" | "num_comments"

interface ArcticResult {
  id: string
  title?: string
  selftext?: string
  body?: string
  author: string
  subreddit: string
  score: number
  created_utc: number
  permalink?: string
  link_id?: string
  url?: string
  num_comments?: number
  upvote_ratio?: number
}

function ResultCard({ result, type }: { result: ArcticResult; type: ResultType }) {
  const [expanded, setExpanded] = useState(false)
  const body = type === "posts" ? (result.selftext || result.title || "") : (result.body || "")
  const isLong = body.length > 300
  const displayed = expanded || !isLong ? body : body.slice(0, 300) + "..."

  const postId =
    type === "comments"
      ? result.link_id?.replace("t3_", "")
      : result.id

  const commentPart =
    type === "comments" ? `_/${result.id}` : ""

  const redditUrl =
    result.permalink
      ? `https://reddit.com${result.permalink}`
      : `https://reddit.com/r/${result.subreddit}/comments/${postId}/${commentPart}`

  const date = result.created_utc
    ? new Date(result.created_utc * 1000).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : ""

  return (
    <div className="border-b border-[#0d0d0d] px-5 py-4 hover:bg-[#050505] transition-colors">
      {type === "posts" && result.title && (
        <div className="text-sm font-semibold text-white mb-2 leading-snug">
          {result.title}
        </div>
      )}

      <div className="text-xs text-[#4b5563] italic leading-relaxed mb-3">
        {displayed}
        {isLong && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="ml-2 text-[#e2e8f0] not-italic hover:text-white transition-colors"
          >
            {expanded ? "show less" : "read more"}
          </button>
        )}
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-[10px] bg-[#111] border border-[#161616] rounded px-1.5 py-0.5 text-[#4b5563]">
          r/{result.subreddit}
        </span>
        <span className="text-[10px] text-[#374151]">
          u/{result.author}
        </span>
        <span className="text-[10px] text-[#2d2d2d]">{date}</span>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-[#22c55e] font-bold font-mono">
            ↑ {result.score.toLocaleString()}
          </span>
        </div>
        {result.num_comments != null && (
          <span className="text-[10px] text-[#2d2d2d]">
            {result.num_comments} comments
          </span>
        )}
        <a
          href={redditUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[10px] text-[#1c1c1c] hover:text-[#94a3b8] ml-auto transition-colors"
        >
          View on Reddit →
        </a>
      </div>
    </div>
  )
}

export default function QueryPage() {
  const [q, setQ] = useState("")
  const [subreddit, setSubreddit] = useState("")
  const [author, setAuthor] = useState("")
  const [after, setAfter] = useState("")
  const [before, setBefore] = useState("")
  const [type, setType] = useState<ResultType>("posts")
  const [sort, setSort] = useState<SortType>("score")
  const [limit, setLimit] = useState("50")
  const [minScore, setMinScore] = useState("0")
  const [results, setResults] = useState<ArcticResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [queryMeta, setQueryMeta] = useState<Record<string, string> | null>(null)

  async function runQuery() {
    if (!q && !subreddit && !author) {
      setError("Enter at least a search query, subreddit, or author.")
      return
    }
    setError("")
    setLoading(true)
    setResults([])
    setQueryMeta(null)

    try {
      const params = new URLSearchParams({
        type,
        sort,
        limit,
        min_score: minScore,
      })
      if (q) params.set("q", q)
      if (subreddit) params.set("subreddit", subreddit)
      if (author) params.set("author", author)
      if (after) params.set("after", new Date(after).toISOString().slice(0, 19))
      if (before) params.set("before", new Date(before).toISOString().slice(0, 19))

      const res = await fetch(`/api/arctic-shift?${params}`)
      const data = await res.json()

      if (!res.ok) {
        setError(data.error ?? "Query failed")
        return
      }

      setResults(data.data ?? [])
      setQueryMeta(data.query)
    } catch {
      setError("Network error — is the API reachable?")
    } finally {
      setLoading(false)
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) runQuery()
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Query builder */}
      <div className="w-[280px] flex-shrink-0 border-r border-[#161616] bg-[#080808] overflow-y-auto p-5 space-y-5">
        <div>
          <div className="text-xs font-bold text-white tracking-wide mb-1">
            Reddit Archive Query
          </div>
          <div className="text-[10px] text-[#374151] leading-relaxed">
            Powered by{" "}
            <a
              href="https://github.com/ArthurHeitmann/arctic_shift"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#e2e8f0] hover:text-white transition-colors"
            >
              Arctic Shift
            </a>{" "}
            by Arthur Heitmann. Searches the complete Reddit archive.
          </div>
        </div>

        {/* Type */}
        <div>
          <div className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase mb-2">
            Content Type
          </div>
          <div className="flex gap-1.5">
            {(["posts", "comments"] as ResultType[]).map((t) => (
              <button
                key={t}
                onClick={() => setType(t)}
                className={`flex-1 py-1.5 rounded text-xs font-medium transition-colors border ${
                  type === t
                    ? "bg-[#111] border-[#2a2a2a] text-white"
                    : "border-[#161616] text-[#4b5563] hover:text-[#94a3b8]"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Search query */}
        <div>
          <label className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase block mb-1.5">
            Search Query
          </label>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={handleKey}
            placeholder='e.g. "hidden gem" small cap'
            className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-xs text-white placeholder-[#2d2d2d] focus:outline-none focus:border-[#2a2a2a]"
          />
          <div className="text-[9px] text-[#1c1c1c] mt-1">
            Supports exact phrases in quotes, AND/OR operators
          </div>
        </div>

        {/* Subreddit */}
        <div>
          <label className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase block mb-1.5">
            Subreddit (optional)
          </label>
          <input
            value={subreddit}
            onChange={(e) => setSubreddit(e.target.value.replace("r/", ""))}
            onKeyDown={handleKey}
            placeholder="e.g. wallstreetbets"
            className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-xs text-white placeholder-[#2d2d2d] focus:outline-none focus:border-[#2a2a2a]"
          />
          <div className="text-[9px] text-[#1c1c1c] mt-1">
            Leave blank to search ALL of Reddit
          </div>
        </div>

        {/* Author */}
        <div>
          <label className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase block mb-1.5">
            Author (optional)
          </label>
          <input
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
            onKeyDown={handleKey}
            placeholder="e.g. deepwater_val"
            className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-xs text-white placeholder-[#2d2d2d] focus:outline-none focus:border-[#2a2a2a]"
          />
        </div>

        {/* Date range */}
        <div>
          <div className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase mb-1.5">
            Date Range (optional)
          </div>
          <div className="space-y-1.5">
            <input
              type="date"
              value={after}
              onChange={(e) => setAfter(e.target.value)}
              className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-xs text-[#94a3b8] focus:outline-none focus:border-[#2a2a2a]"
            />
            <div className="text-[9px] text-[#1c1c1c] text-center">to</div>
            <input
              type="date"
              value={before}
              onChange={(e) => setBefore(e.target.value)}
              className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-xs text-[#94a3b8] focus:outline-none focus:border-[#2a2a2a]"
            />
          </div>
        </div>

        {/* Sort */}
        <div>
          <label className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase block mb-1.5">
            Sort By
          </label>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortType)}
            className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-3 py-2 text-xs text-white focus:outline-none focus:border-[#2a2a2a]"
          >
            <option value="score">Score (highest first)</option>
            <option value="created_utc">Date (newest first)</option>
            <option value="num_comments">Most commented</option>
          </select>
        </div>

        {/* Limit + min score */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase block mb-1.5">
              Limit
            </label>
            <select
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-2 py-2 text-xs text-white focus:outline-none"
            >
              {["10", "25", "50", "100"].map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase block mb-1.5">
              Min Score
            </label>
            <input
              type="number"
              min="0"
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              className="w-full bg-[#0d0d0d] border border-[#1c1c1c] rounded px-2 py-2 text-xs text-white focus:outline-none focus:border-[#2a2a2a]"
            />
          </div>
        </div>

        {/* Preset queries */}
        <div>
          <div className="text-[9px] text-[#2d2d2d] tracking-[0.12em] uppercase mb-2">
            Preset Queries
          </div>
          <div className="space-y-1">
            {[
              { label: "Hidden gems", q: "hidden gem small cap stock" },
              { label: "Under the radar", q: "under the radar ticker" },
              { label: "No one talking about", q: "no one is talking about stock" },
              { label: "Micro cap DD", q: "micro cap due diligence" },
              { label: "Short squeeze potential", q: "short squeeze float" },
              { label: "FDA catalyst", q: "FDA approval catalyst PDUFA" },
            ].map((preset) => (
              <button
                key={preset.label}
                onClick={() => setQ(preset.q)}
                className="block w-full text-left text-[10px] text-[#374151] hover:text-[#94a3b8] py-1 px-2 rounded hover:bg-[#111] transition-colors"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={runQuery}
          disabled={loading}
          className="w-full py-2.5 rounded-lg border text-sm font-semibold transition-colors bg-[#111] border-[#2a2a2a] text-[#e2e8f0] hover:bg-[#161616] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "Searching..." : "Run Query →"}
        </button>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        <div className="border-b border-[#111] px-5 py-3 bg-[#050505] flex items-center gap-3">
          <div className="text-xs font-bold text-white tracking-wide">
            Reddit Archive
          </div>
          {queryMeta && (
            <span className="text-[10px] text-[#4b5563]">
              {results.length} results
              {queryMeta.q && ` for "${queryMeta.q}"`}
              {queryMeta.subreddit && ` in r/${queryMeta.subreddit}`}
            </span>
          )}
          <a
            href="https://github.com/ArthurHeitmann/arctic_shift"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-[9px] text-[#1c1c1c] hover:text-[#4b5563] transition-colors"
          >
            Arctic Shift by Arthur Heitmann
          </a>
        </div>

        {!loading && !queryMeta && (
          <div className="flex flex-col items-center justify-center h-[60vh] text-center">
            <div className="text-3xl font-bold tracking-[0.1em] uppercase text-[#111] mb-3">
              QUERY
            </div>
            <div className="text-xs text-[#2d2d2d] max-w-sm leading-relaxed">
              Search the complete Reddit archive. Every post and comment
              from every public subreddit, going back to Reddit&apos;s founding.
              Find what was being said about a stock on any date.
            </div>
            <div className="mt-6 space-y-1.5 text-[10px] text-[#1c1c1c]">
              <div>Try: &quot;NVDA supply chain&quot; before:2024-01-01</div>
              <div>Try: author:deepwater_val in r/SecurityAnalysis</div>
              <div>Try: &quot;micro cap hidden gem&quot; sorted by score</div>
            </div>
          </div>
        )}

        {loading && (
          <div className="p-8 text-center text-[#2d2d2d] text-xs">
            Searching the Reddit archive...
          </div>
        )}

        {error && (
          <div className="mx-5 mt-4 p-3 bg-[#140305] border border-[#280510] rounded-lg text-xs text-[#f87171]">
            {error}
          </div>
        )}

        {!loading && results.length === 0 && queryMeta && !error && (
          <div className="p-8 text-center text-[#2d2d2d] text-xs">
            No results found. Try broadening your query or adjusting the date range.
          </div>
        )}

        {results.map((result) => (
          <ResultCard
            key={`${type}-${result.id}`}
            result={result}
            type={type}
          />
        ))}
      </div>
    </div>
  )
}
