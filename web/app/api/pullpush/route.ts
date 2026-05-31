/**
 * Proxy route for PullPush API.
 *
 * PullPush (https://pullpush.io) is the community continuation of Pushshift —
 * the most comprehensive Reddit archive ever built, covering posts and comments
 * back to 2005. No authentication required.
 */
import { NextRequest } from "next/server"

const BASE = "https://api.pullpush.io/reddit/search"
const UA = "argus-personal/0.1 (https://github.com/makhskham/argus)"

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl

  const type = searchParams.get("type") ?? "posts"
  const q = searchParams.get("q") ?? ""
  const subreddit = searchParams.get("subreddit") ?? ""
  const author = searchParams.get("author") ?? ""
  const after = searchParams.get("after") ?? ""
  const before = searchParams.get("before") ?? ""
  const sort = searchParams.get("sort") ?? "score"
  const limit = Math.min(parseInt(searchParams.get("limit") ?? "50"), 100)

  const endpoint =
    type === "comments"
      ? `${BASE}/comment`
      : `${BASE}/submission`

  const params = new URLSearchParams({
    size: String(limit),
    sort,
    sort_type: sort,
  })
  if (q) params.set("q", q)
  if (subreddit) params.set("subreddit", subreddit)
  if (author) params.set("author", author)
  if (after) params.set("after", String(Math.floor(new Date(after).getTime() / 1000)))
  if (before) params.set("before", String(Math.floor(new Date(before).getTime() / 1000)))

  try {
    const res = await fetch(`${endpoint}?${params}`, {
      headers: { "User-Agent": UA },
      next: { revalidate: 0 },
    })

    if (!res.ok) {
      return Response.json(
        { error: `PullPush returned ${res.status}` },
        { status: res.status }
      )
    }

    const data = await res.json()
    const results = data.data ?? []

    return Response.json({
      data: results,
      count: results.length,
      query: { type, q, subreddit, author, after, before, sort, limit },
      source: "PullPush — https://pullpush.io (Pushshift community continuation)",
    })
  } catch {
    return Response.json({ error: "PullPush unreachable" }, { status: 503 })
  }
}
