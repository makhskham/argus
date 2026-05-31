# Argus

![Cover Art Placeholder](https://via.placeholder.com/1200x400?text=Argus+-+Financial+Intelligence+Platform)

> *Every signal. Every corner. Nothing missed.*

---

## Origin

The name comes from Argus Panoptes, the all-seeing giant of Greek mythology whose hundred eyes watched over everything simultaneously. The idea came from a frustration that most retail investors are playing the market with one eye closed. The information exists. Obscure subreddits discuss niche companies months before analysts notice them. Buried comments on r/SecurityAnalysis contain backtested data that never makes it to Bloomberg. An SEC 8-K filing announces a $650 million deal at 6am and the retail investor finds out at market close when the price has already moved. Argus was built to see all of it, process all of it, and surface the signal from the noise so that one person with a modest budget can make decisions with the same informational depth as a professional desk.

## What Makes It Different

**Niche company detection.** The recommendation engine does not simply rank by total mention count, which would always surface NVIDIA and Apple at the top. It tracks mention velocity: how fast a ticker is gaining attention relative to where it was six hours ago. A company mentioned once last week and twenty times today scores higher on the emerging list than a household name with steady coverage. This is how you find the stock at $2 before it reaches $40.

**Budget-aware intelligence.** When you set your total budget and your maximum per-share price, the system filters every recommendation to what you can actually buy. A $50 per-share budget opens the micro-cap and small-cap universe, where the most asymmetric returns tend to live.

**Forum depth that normal investors skip.** Argus scrapes 25+ communities including r/SecurityAnalysis, r/algotrading, r/pennystocks, r/MicroCapStocks, r/OTCstocks, Stocktwits, SEC EDGAR filings, Seeking Alpha, and more. Every post, every comment thread, every reply chain. The kind of due diligence that would take a human analyst forty hours to do manually runs on a cron schedule.

**Trusted source weighting.** Reddit users with consistently high upvotes, strong community response, and verified directional accuracy get elevated trust scores. Their posts get 2x weighting in the sentiment calculation. Their names appear in a Trusted Voices panel so you can see who the platform learned to rely on.

**Shariah compliance built in.** Every ticker is screened against Zoya API and the Dow Jones Islamic Market Index. A green crescent symbol appears next to every compliant ticker across every page. The entire platform can be filtered to halal-only view with a single toggle.

## Architecture

```mermaid
sequenceDiagram
    participant Scheduler as Go Scheduler (Asynq)
    participant Redis
    participant Worker as Python Workers (PRAW, Playwright)
    participant DB as PostgreSQL + pgvector
    participant Claude as Claude API
    participant Voyage as Voyage AI
    participant API as Go REST API
    participant Web as Next.js Frontend

    Scheduler->>Redis: dispatch scrape jobs (cron)
    Redis->>Worker: job picked up
    Worker->>Worker: scrape Reddit posts + comments (25 subreddits)
    Worker->>Worker: scrape Stocktwits, Seeking Alpha, SEC EDGAR
    Worker->>DB: store raw signals
    Worker->>Worker: calculate mention velocity
    Worker->>DB: update ticker_velocity, emerging_tickers

    DB->>Claude: batch posts for signal extraction
    Claude->>DB: tickers, sentiment, confidence, key_quote

    DB->>Voyage: post text for embeddings
    Voyage->>DB: 1024-dim vectors stored in pgvector

    DB->>API: recommendations query (ranked, budget-filtered, halal-filtered)
    API->>Web: REST JSON
    Web->>Web: render dashboard, intelligence feed, hidden gems panel

    Web->>Claude: AI chat message (Opus 4.8)
    Claude->>Web: streaming response with source citations
```

## Key Design Decisions

**Velocity over volume for rankings.** A company mentioned 5 times in the last six hours when it had zero mentions the six hours before that scores higher than a well-covered large cap. This keeps the emerging company detection working even when database history is short.

**Go orchestrates, Python scrapes.** Python's PRAW library is the correct tool for Reddit. It handles authentication, rate limiting, pagination, and nested comment tree traversal automatically. Go's goroutines coordinate the jobs and process the results through Claude. Each service does what it does best.

**sqlc over an ORM.** Every database query is written in raw SQL. sqlc generates type-safe Go functions from those queries at build time. There are no hidden queries, no N+1 problems, and no ORM abstraction obscuring what hits the database.

**Voyage AI voyage-finance-2 for embeddings.** Generic embedding models embed a post saying "the float is getting squeezed" far from "short squeeze." Voyage finance-2 was trained on SEC filings, earnings calls, and analyst reports. The semantic search across signals is meaningfully more accurate.

**nuqs for URL state.** Date range filters, the halal toggle, active tabs, and ticker filters all live in the URL. Any view is bookmarkable and shareable. The back button works correctly. This is what distinguishes a professional tool from a prototype.

## Quick Start

### Prerequisites

- Go 1.23+
- Python 3.12+
- Node.js 20+ and pnpm
- Docker (for local PostgreSQL and Redis)

### Local Development

```bash
# Start database and Redis
make up

# Run database migrations
make migrate

# Start the Go API
make api

# Start Python scrapers (in a separate terminal)
make scraper

# Start the frontend (in a separate terminal)
make web
```

Environment variables required - copy and fill in:

```bash
# api/.env
DATABASE_URL=postgres://argus:argus@localhost:5432/argus?sslmode=disable
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=your_key
VOYAGE_API_KEY=your_key
POLYGON_API_KEY=your_key
ZOYA_API_KEY=your_key

# scraper/.env
DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret

# web/.env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_key
CLERK_SECRET_KEY=your_key
NEXT_PUBLIC_API_URL=http://localhost:8080
ANTHROPIC_API_KEY=your_key
```

### Full Cluster (Docker Compose)

```bash
docker compose up
```

## Project Structure

```
argus/
├── api/                        Go backend
│   ├── cmd/
│   │   ├── api/main.go         HTTP server entrypoint
│   │   └── migrate/main.go     Database migration runner
│   ├── internal/
│   │   ├── config/             Environment configuration
│   │   └── handler/            HTTP handlers (recommendations, signals, users)
│   ├── db/
│   │   └── queries/            Raw SQL queries (signals, recommendations, users)
│   ├── migrations/             PostgreSQL migration files
│   └── Dockerfile
├── scraper/                    Python scraping workers
│   └── scraper/
│       ├── reddit.py           Reddit public JSON API (25 subreddits, no auth)
│       ├── arctic_shift.py     Arctic Shift integration (full Reddit archive search)
│       ├── stocktwits.py       Stocktwits real-time sentiment
│       ├── seeking_alpha.py    Seeking Alpha analyst articles
│       ├── velocity.py         Mention velocity and emerging ticker detection
│       ├── worker.py           Main scrape cycle orchestration
│       ├── models.py           Pydantic data models
│       └── config.py           Environment configuration
├── web/                        Next.js 15 frontend
│   ├── app/
│   │   ├── (app)/              Authenticated app pages
│   │   │   ├── dashboard/      Command Center
│   │   │   ├── intelligence/   Signal feed with filters
│   │   │   ├── query/          Reddit archive manual query (Arctic Shift)
│   │   │   ├── chat/           AI chat (Claude Opus 4.8)
│   │   │   ├── stocks/[ticker] Stock deep dive
│   │   │   ├── profile/        Budget, goals, halal filter
│   │   │   └── ...             Other pages
│   │   ├── api/chat/           Streaming chat API route
│   │   └── api/arctic-shift/   Proxy route for Arctic Shift queries
│   ├── components/
│   │   ├── ui/                 Design system components
│   │   ├── recommendation-table.tsx
│   │   ├── hidden-gems-panel.tsx
│   │   └── breaking-signals-panel.tsx
│   └── lib/api.ts              API client with typed interfaces
├── docker-compose.yml
├── Makefile
└── .github/workflows/ci.yml
```

## Open Source Tools Used

**Data Sources and Archives**
- **[Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift)** by Arthur Heitmann - Community-maintained archive of all public Reddit data. Powers the Archive Query page and the hidden gem discovery pipeline. Enables searching the complete Reddit history across every public subreddit with no authentication required.
- **[PullPush](https://pullpush.io)** - Community continuation of Pushshift. Provides deep historical Reddit data going back to 2005, used for niche discovery queries and ticker history lookups.
- **[Twikit](https://github.com/d60/twikit)** - Python library for accessing Twitter/X without an official API key. Optional component that enables fintwit (financial Twitter) signal collection.
- **[Stocktwits](https://stocktwits.com)** - Real-time retail investor sentiment via their public API endpoints.
- **[Seeking Alpha](https://seekingalpha.com)** - Analyst articles accessed via their frontend API.

**Libraries**
- **[TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts)** - Professional financial charting library, the same engine used by TradingView.com
- **[PRAW](https://github.com/praw-dev/praw)** - Python Reddit API Wrapper (used when official credentials are available)
- **[httpx](https://github.com/encode/httpx)** - Async HTTP client for Python
- **[Pydantic](https://github.com/pydantic/pydantic)** - Data validation for scraped content

## License

MIT
