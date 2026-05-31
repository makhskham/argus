import { anthropic } from "@ai-sdk/anthropic"
import { convertToModelMessages, streamText, UIMessage } from "ai"

export const maxDuration = 60

const SYSTEM = `You are Argus Intelligence — an AI investment analyst backed by real-time data scraped from Reddit investment communities, SEC EDGAR filings, Stocktwits, Seeking Alpha, and 20+ financial sources.

Your role: provide actionable, sourced investment intelligence. Every claim must reference its source. When you do not have specific scraped data, say so clearly and use your general financial knowledge.

Key behaviors:
- Always cite sources when making claims (e.g. "r/SecurityAnalysis · u/deepwater_val · 2,841 upvotes")
- For Shariah compliance questions, reference Zoya API / DJIMI / MSCI Islamic Index
- For directional calls, provide a confidence level and timeframe
- Be direct — this is for real investment decisions, not education
- Flag if something is speculation vs confirmed (SEC filing, earnings call, etc.)
- Format responses clearly with sections when appropriate`

export async function POST(req: Request) {
  const { messages, userProfile }: { messages: UIMessage[]; userProfile?: Record<string, unknown> } = await req.json()
  const systemWithProfile = userProfile
    ? `${SYSTEM}\n\nUser profile: Budget $${userProfile.budget ?? "unknown"}, Risk tolerance: ${userProfile.risk_tolerance ?? "moderate"}, Goal: ${userProfile.investing_goal ?? "not set"}, Halal filter: ${userProfile.halal_filter ? "ACTIVE — only recommend Shariah-compliant investments" : "off"}.`
    : SYSTEM
  const result = streamText({
    model: anthropic("claude-opus-4-5"),
    system: systemWithProfile,
    messages: await convertToModelMessages(messages),
  })
  return result.toUIMessageStreamResponse()
}
