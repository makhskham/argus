/**
 * Proxy API route for Arctic Shift queries.
 *
 * Arctic Shift (https://github.com/ArthurHeitmann/arctic_shift) by Arthur Heitmann
 * provides a free API to search the complete Reddit archive.
 * This route forwards queries from the Argus frontend to the Arctic Shift API.
 */
import { NextRequest } from "next/server"

const BASE = "https://arctic-shift.photon-reddit.com/api"
const UA = "argus-personal/0.1 (https://github.com/makhskham/argus)"

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl

  const type = searchParams.get("type") ?? "posts" // posts | comments
  const q = searchParams.get("q") ?? ""
  const subreddit = searchParams.get("subreddit") ?? ""
  const author = searchParams.get("author") ?? ""
  const after = searchParams.get("after") ?? ""
  const before = searchParams.get("before") ?? ""
  const sort = searchParams.get("sort") ?? "score"
  const limit = Math.min(parseInt(searchParams.get("limit") ?? "50"), 100)
  const minScore = parseInt(searchParams.get("min_score") ?? "0")

  const endpoint =
    type === "comments"
      ? `${BASE}/comments/search`
      : `${BASE}/posts/search`

  const params = new URLSearchParams()
  if (q) params.set("q", q)
  if (subreddit) params.set("subreddit", subreddit)
  if (author) params.set("author", author)
  if (after) params.set("after", after)
  if (before) params.set("before", before)
  params.set("sort", sort)
  params.set("limit", String(limit))

  try {
    const res = await fetch(`${endpoint}?${params}`, {
      headers: { "User-Agent": UA },
      next: { revalidate: 0 },
    })

    if (!res.ok) {
      return Response.json(
        { error: `Arctic Shift returned ${res.status}` },
        { status: res.status }
      )
    }

    const data = await res.json()
    let results = data.data ?? []

    // Apply min score filter client-side
    if (minScore > 0) {
      results = results.filter(
        (r: { score?: number }) => (r.score ?? 0) >= minScore
      )
    }

    return Response.json({
      data: results,
      count: results.length,
      query: { type, q, subreddit, author, after, before, sort, limit },
      source: "Arctic Shift — https://github.com/ArthurHeitmann/arctic_shift",
    })
  } catch (err) {
    return Response.json({ error: "Arctic Shift unreachable" }, { status: 503 })
  }
}
