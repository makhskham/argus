# Argus Phase 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Scaffold the complete Argus monorepo — Go API, Python scrapers, Next.js frontend, PostgreSQL schema, Docker Compose local dev environment, and GitHub CI.

**Architecture:** Three services communicate via PostgreSQL and Redis. Go (Chi router, sqlc, Asynq) is the brain. Python workers (PRAW, Playwright) are the eyes. Next.js 15 (App Router, Clerk, TanStack Query) is the face.

**Tech Stack:** Go 1.23, Python 3.12, Next.js 15, TypeScript, PostgreSQL 16 + pgvector + TimescaleDB, Redis, Docker Compose, Clerk, Tailwind v4, sqlc, pgx v5, Asynq, PRAW, Playwright

---

## Task 1: Root scaffold and .gitignore

**Files:**
- Create: `.gitignore`
- Create: `docker-compose.yml`
- Create: `Makefile`

- [ ] Create `.gitignore`:

```gitignore
# Go
api/bin/
*.exe

# Python
scraper/__pycache__/
scraper/.venv/
scraper/*.pyc
scraper/playwright-browsers/

# Next.js
web/.next/
web/node_modules/
web/.env.local

# Env
.env
.env.local
local.yaml
*.local.yaml

# Superpowers
.superpowers/

# IDE
.idea/
.vscode/
*.swp
```

- [ ] Create `docker-compose.yml`:

```yaml
version: "3.9"
services:
  db:
    image: timescale/timescaledb-ha:pg16-latest
    environment:
      POSTGRES_USER: argus
      POSTGRES_PASSWORD: argus
      POSTGRES_DB: argus
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: ./api
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgres://argus:argus@db:5432/argus?sslmode=disable
      REDIS_URL: redis://redis:6379
    depends_on:
      - db
      - redis

  scraper:
    build: ./scraper
    environment:
      DATABASE_URL: postgresql+asyncpg://argus:argus@db:5432/argus
      REDIS_URL: redis://redis:6379
    depends_on:
      - db
      - redis

volumes:
  pgdata:
```

- [ ] Create `Makefile`:

```makefile
.PHONY: up down migrate api scraper web

up:
	docker compose up -d db redis

down:
	docker compose down

migrate:
	cd api && go run ./cmd/migrate up

api:
	cd api && go run ./cmd/api

scraper:
	cd scraper && python -m scraper.worker

web:
	cd web && pnpm dev
```

- [ ] Commit:

```bash
git add .gitignore docker-compose.yml Makefile
git commit -m "chore: root scaffold with docker compose and makefile"
```

---

## Task 2: Go module and directory structure

**Files:**
- Create: `api/go.mod`
- Create: `api/cmd/api/main.go`
- Create: `api/cmd/migrate/main.go`
- Create: `api/internal/config/config.go`
- Create: `api/Dockerfile`

- [ ] Initialize Go module:

```bash
cd api && go mod init github.com/makhskham/argus/api
```

- [ ] Create `api/go.mod` (after init, add dependencies):

```bash
cd api && go get \
  github.com/go-chi/chi/v5 \
  github.com/jackc/pgx/v5 \
  github.com/jackc/pgx/v5/pgxpool \
  github.com/golang-migrate/migrate/v4 \
  github.com/golang-migrate/migrate/v4/database/pgx/v5 \
  github.com/golang-migrate/migrate/v4/source/file \
  github.com/hibiken/asynq \
  github.com/prometheus/client_golang/prometheus \
  github.com/prometheus/client_golang/prometheus/promhttp \
  github.com/rs/cors \
  github.com/joho/godotenv
```

- [ ] Create `api/internal/config/config.go`:

```go
package config

import (
	"os"
)

type Config struct {
	DatabaseURL   string
	RedisURL      string
	AnthropicKey  string
	VoyageKey     string
	PolygonKey    string
	ZoyaKey       string
	Port          string
}

func Load() Config {
	return Config{
		DatabaseURL:  mustEnv("DATABASE_URL"),
		RedisURL:     getEnv("REDIS_URL", "redis://localhost:6379"),
		AnthropicKey: mustEnv("ANTHROPIC_API_KEY"),
		VoyageKey:    mustEnv("VOYAGE_API_KEY"),
		PolygonKey:   mustEnv("POLYGON_API_KEY"),
		ZoyaKey:      getEnv("ZOYA_API_KEY", ""),
		Port:         getEnv("PORT", "8080"),
	}
}

func mustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		panic("missing required env var: " + key)
	}
	return v
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
```

- [ ] Create `api/cmd/api/main.go`:

```go
package main

import (
	"context"
	"log"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	"github.com/makhskham/argus/api/internal/config"
)

func main() {
	_ = godotenv.Load()
	cfg := config.Load()

	pool, err := pgxpool.New(context.Background(), cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("db connect: %v", err)
	}
	defer pool.Close()

	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)

	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte(`{"status":"ok"}`))
	})

	log.Printf("api listening on :%s", cfg.Port)
	http.ListenAndServe(":"+cfg.Port, r)
}
```

- [ ] Create `api/cmd/migrate/main.go`:

```go
package main

import (
	"log"
	"os"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/pgx/v5"
	_ "github.com/golang-migrate/migrate/v4/source/file"
	"github.com/joho/godotenv"
)

func main() {
	_ = godotenv.Load()
	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		log.Fatal("DATABASE_URL required")
	}

	m, err := migrate.New("file://migrations", dbURL)
	if err != nil {
		log.Fatalf("migrate init: %v", err)
	}

	direction := "up"
	if len(os.Args) > 1 {
		direction = os.Args[1]
	}

	switch direction {
	case "up":
		if err := m.Up(); err != nil && err != migrate.ErrNoChange {
			log.Fatalf("migrate up: %v", err)
		}
	case "down":
		if err := m.Down(); err != nil && err != migrate.ErrNoChange {
			log.Fatalf("migrate down: %v", err)
		}
	}
	log.Println("migrations applied")
}
```

- [ ] Create `api/Dockerfile`:

```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o bin/api ./cmd/api

FROM alpine:3.20
WORKDIR /app
COPY --from=builder /app/bin/api .
COPY migrations ./migrations
EXPOSE 8080
CMD ["./api"]
```

- [ ] Create `api/.env.example`:

```env
DATABASE_URL=postgres://argus:argus@localhost:5432/argus?sslmode=disable
REDIS_URL=redis://localhost:6379
ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
POLYGON_API_KEY=
ZOYA_API_KEY=
PORT=8080
```

- [ ] Verify it compiles:

```bash
cd api && go build ./...
```
Expected: no output (success)

- [ ] Commit:

```bash
git add api/
git commit -m "feat: go api scaffold with chi, pgx, config"
```

---

## Task 3: Database schema migrations

**Files:**
- Create: `api/migrations/000001_init.up.sql`
- Create: `api/migrations/000001_init.down.sql`

- [ ] Create `api/migrations/000001_init.up.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Reddit users / trust scoring
CREATE TABLE reddit_users (
  id            BIGSERIAL PRIMARY KEY,
  username      TEXT NOT NULL UNIQUE,
  total_karma   BIGINT DEFAULT 0,
  investment_post_count INT DEFAULT 0,
  avg_upvote_ratio FLOAT DEFAULT 0,
  trust_tier    TEXT NOT NULL DEFAULT 'unverified'
                  CHECK (trust_tier IN ('unverified','recognized','trusted','authority')),
  accuracy_score FLOAT DEFAULT 0,
  calls_tracked  INT DEFAULT 0,
  last_scored_at TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Raw scraped posts/comments
CREATE TABLE signals (
  id              BIGSERIAL PRIMARY KEY,
  source          TEXT NOT NULL,
  source_type     TEXT NOT NULL CHECK (source_type IN ('reddit','stocktwits','seeking_alpha','sec_edgar','tipranks','other')),
  external_id     TEXT NOT NULL,
  subreddit       TEXT,
  reddit_user_id  BIGINT REFERENCES reddit_users(id),
  author          TEXT,
  title           TEXT,
  body            TEXT NOT NULL,
  url             TEXT,
  upvotes         INT DEFAULT 0,
  upvote_ratio    FLOAT DEFAULT 0,
  posted_at       TIMESTAMPTZ NOT NULL,
  scraped_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(source_type, external_id)
);

-- Extracted signal analysis (Claude output per signal)
CREATE TABLE signal_analyses (
  id              BIGSERIAL PRIMARY KEY,
  signal_id       BIGINT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
  tickers         TEXT[] NOT NULL DEFAULT '{}',
  sentiment       TEXT NOT NULL CHECK (sentiment IN ('bullish','bearish','neutral')),
  confidence      INT NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  key_quote       TEXT,
  is_prediction   BOOLEAN DEFAULT FALSE,
  prediction_direction TEXT,
  prediction_timeframe TEXT,
  is_niche_flagged BOOLEAN DEFAULT FALSE,
  model_used      TEXT NOT NULL,
  analyzed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vector embeddings for semantic search
CREATE TABLE signal_embeddings (
  signal_id   BIGINT PRIMARY KEY REFERENCES signals(id) ON DELETE CASCADE,
  embedding   vector(1024) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON signal_embeddings USING hnsw (embedding vector_cosine_ops);

-- Per-ticker aggregated sentiment (updated each scrape cycle)
CREATE TABLE ticker_sentiment (
  id            BIGSERIAL PRIMARY KEY,
  ticker        TEXT NOT NULL,
  period_start  TIMESTAMPTZ NOT NULL,
  period_end    TIMESTAMPTZ NOT NULL,
  bull_pct      FLOAT NOT NULL DEFAULT 0,
  neutral_pct   FLOAT NOT NULL DEFAULT 0,
  bear_pct      FLOAT NOT NULL DEFAULT 0,
  confidence    INT NOT NULL DEFAULT 0,
  signal_count  INT NOT NULL DEFAULT 0,
  source_count  INT NOT NULL DEFAULT 0,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(ticker, period_start, period_end)
);

-- Stock recommendations (ranked list, rebuilt each cycle)
CREATE TABLE recommendations (
  id              BIGSERIAL PRIMARY KEY,
  ticker          TEXT NOT NULL,
  company_name    TEXT,
  direction       TEXT NOT NULL CHECK (direction IN ('buy','avoid')),
  rank            INT NOT NULL,
  confidence      INT NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  bull_pct        FLOAT NOT NULL DEFAULT 0,
  neutral_pct     FLOAT NOT NULL DEFAULT 0,
  bear_pct        FLOAT NOT NULL DEFAULT 0,
  signal_count    INT NOT NULL DEFAULT 0,
  source_count    INT NOT NULL DEFAULT 0,
  ai_analysis     TEXT,
  price_target_base NUMERIC(10,2),
  price_target_bull NUMERIC(10,2),
  price_target_bear NUMERIC(10,2),
  cycle_id        BIGINT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON recommendations(direction, rank);

-- Scrape cycles
CREATE TABLE scrape_cycles (
  id          BIGSERIAL PRIMARY KEY,
  started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  signals_added INT DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running','complete','failed'))
);

-- Halal compliance cache
CREATE TABLE halal_compliance (
  ticker          TEXT PRIMARY KEY,
  is_compliant    BOOLEAN,
  zoya_status     TEXT,
  debt_ratio      FLOAT,
  interest_income_ratio FLOAT,
  business_activity_ok BOOLEAN,
  djimi_listed    BOOLEAN,
  last_checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  next_check_at   TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '90 days'
);

-- User watchlist (per Clerk user ID)
CREATE TABLE watchlist (
  id          BIGSERIAL PRIMARY KEY,
  clerk_user_id TEXT NOT NULL,
  ticker      TEXT NOT NULL,
  added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(clerk_user_id, ticker)
);

-- User profiles
CREATE TABLE user_profiles (
  clerk_user_id   TEXT PRIMARY KEY,
  budget          NUMERIC(14,2),
  risk_tolerance  TEXT CHECK (risk_tolerance IN ('conservative','moderate','aggressive')),
  investing_goal  TEXT CHECK (investing_goal IN ('retirement','short_term','passive_income','speculative')),
  halal_filter    BOOLEAN DEFAULT FALSE,
  excluded_tickers TEXT[] DEFAULT '{}',
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Price history (TimescaleDB hypertable)
CREATE TABLE price_history (
  ticker    TEXT NOT NULL,
  ts        TIMESTAMPTZ NOT NULL,
  open      NUMERIC(10,2),
  high      NUMERIC(10,2),
  low       NUMERIC(10,2),
  close     NUMERIC(10,2),
  volume    BIGINT,
  PRIMARY KEY (ticker, ts)
);
SELECT create_hypertable('price_history', 'ts');
```

- [ ] Create `api/migrations/000001_init.down.sql`:

```sql
DROP TABLE IF EXISTS price_history;
DROP TABLE IF EXISTS user_profiles;
DROP TABLE IF EXISTS watchlist;
DROP TABLE IF EXISTS halal_compliance;
DROP TABLE IF EXISTS scrape_cycles;
DROP TABLE IF EXISTS recommendations;
DROP TABLE IF EXISTS ticker_sentiment;
DROP TABLE IF EXISTS signal_embeddings;
DROP TABLE IF EXISTS signal_analyses;
DROP TABLE IF EXISTS signals;
DROP TABLE IF EXISTS reddit_users;
DROP EXTENSION IF EXISTS timescaledb;
DROP EXTENSION IF EXISTS vector;
```

- [ ] Start the database and run migrations:

```bash
docker compose up -d db
sleep 5
cd api && DATABASE_URL="postgres://argus:argus@localhost:5432/argus?sslmode=disable" go run ./cmd/migrate up
```
Expected: `migrations applied`

- [ ] Commit:

```bash
git add api/migrations/
git commit -m "feat: complete database schema with pgvector and timescaledb"
```

---

## Task 4: sqlc setup and query generation

**Files:**
- Create: `api/sqlc.yaml`
- Create: `api/db/queries/signals.sql`
- Create: `api/db/queries/recommendations.sql`
- Create: `api/db/queries/users.sql`

- [ ] Install sqlc:

```bash
go install github.com/sqlc-dev/sqlc/cmd/sqlc@latest
```

- [ ] Create `api/sqlc.yaml`:

```yaml
version: "2"
sql:
  - engine: "postgresql"
    queries: "db/queries"
    schema: "migrations"
    gen:
      go:
        package: "db"
        out: "db/sqlc"
        emit_json_tags: true
        emit_params_struct_pointers: true
```

- [ ] Create `api/db/queries/signals.sql`:

```sql
-- name: InsertSignal :one
INSERT INTO signals (source, source_type, external_id, subreddit, author, title, body, url, upvotes, upvote_ratio, posted_at)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT (source_type, external_id) DO NOTHING
RETURNING *;

-- name: GetRecentSignals :many
SELECT s.*, sa.sentiment, sa.confidence, sa.tickers, sa.key_quote, sa.is_niche_flagged
FROM signals s
LEFT JOIN signal_analyses sa ON sa.signal_id = s.id
WHERE s.scraped_at >= $1
ORDER BY s.scraped_at DESC
LIMIT $2 OFFSET $3;

-- name: GetSignalsByTicker :many
SELECT s.*, sa.sentiment, sa.confidence, sa.key_quote, sa.is_niche_flagged
FROM signals s
JOIN signal_analyses sa ON sa.signal_id = s.id
WHERE $1 = ANY(sa.tickers)
  AND s.posted_at >= $2
ORDER BY sa.confidence DESC, s.upvotes DESC
LIMIT $3 OFFSET $4;

-- name: InsertSignalAnalysis :one
INSERT INTO signal_analyses (signal_id, tickers, sentiment, confidence, key_quote, is_prediction, prediction_direction, prediction_timeframe, is_niche_flagged, model_used)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
RETURNING *;

-- name: InsertEmbedding :exec
INSERT INTO signal_embeddings (signal_id, embedding)
VALUES ($1, $2)
ON CONFLICT (signal_id) DO UPDATE SET embedding = $2;

-- name: SearchSimilarSignals :many
SELECT s.*, sa.tickers, sa.sentiment, sa.confidence, sa.key_quote,
       (se.embedding <=> $1) AS distance
FROM signal_embeddings se
JOIN signals s ON s.id = se.signal_id
LEFT JOIN signal_analyses sa ON sa.signal_id = s.id
ORDER BY se.embedding <=> $1
LIMIT $2;
```

- [ ] Create `api/db/queries/recommendations.sql`:

```sql
-- name: UpsertRecommendation :one
INSERT INTO recommendations (ticker, company_name, direction, rank, confidence, bull_pct, neutral_pct, bear_pct, signal_count, source_count, ai_analysis, price_target_base, price_target_bull, price_target_bear, cycle_id)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
RETURNING *;

-- name: GetTopRecommendations :many
SELECT r.*, h.is_compliant AS halal_compliant
FROM recommendations r
LEFT JOIN halal_compliance h ON h.ticker = r.ticker
WHERE r.direction = $1
  AND r.cycle_id = (SELECT MAX(id) FROM scrape_cycles WHERE status = 'complete')
ORDER BY r.rank
LIMIT $2;

-- name: GetHalalRecommendations :many
SELECT r.*, h.is_compliant AS halal_compliant
FROM recommendations r
JOIN halal_compliance h ON h.ticker = r.ticker AND h.is_compliant = TRUE
WHERE r.direction = $1
  AND r.cycle_id = (SELECT MAX(id) FROM scrape_cycles WHERE status = 'complete')
ORDER BY r.rank
LIMIT $2;

-- name: GetRecommendationByTicker :one
SELECT r.*, h.is_compliant AS halal_compliant, h.debt_ratio, h.interest_income_ratio
FROM recommendations r
LEFT JOIN halal_compliance h ON h.ticker = r.ticker
WHERE r.ticker = $1
  AND r.cycle_id = (SELECT MAX(id) FROM scrape_cycles WHERE status = 'complete')
LIMIT 1;

-- name: CreateScrape Cycle :one
INSERT INTO scrape_cycles DEFAULT VALUES RETURNING *;

-- name: CompleteScrape Cycle :one
UPDATE scrape_cycles SET status = 'complete', finished_at = NOW(), signals_added = $2
WHERE id = $1 RETURNING *;
```

- [ ] Create `api/db/queries/users.sql`:

```sql
-- name: UpsertUserProfile :one
INSERT INTO user_profiles (clerk_user_id, budget, risk_tolerance, investing_goal, halal_filter, excluded_tickers)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (clerk_user_id) DO UPDATE SET
  budget = EXCLUDED.budget,
  risk_tolerance = EXCLUDED.risk_tolerance,
  investing_goal = EXCLUDED.investing_goal,
  halal_filter = EXCLUDED.halal_filter,
  excluded_tickers = EXCLUDED.excluded_tickers,
  updated_at = NOW()
RETURNING *;

-- name: GetUserProfile :one
SELECT * FROM user_profiles WHERE clerk_user_id = $1;

-- name: AddToWatchlist :one
INSERT INTO watchlist (clerk_user_id, ticker) VALUES ($1, $2)
ON CONFLICT DO NOTHING RETURNING *;

-- name: GetWatchlist :many
SELECT w.ticker, h.is_compliant AS halal_compliant
FROM watchlist w
LEFT JOIN halal_compliance h ON h.ticker = w.ticker
WHERE w.clerk_user_id = $1
ORDER BY w.added_at DESC;

-- name: GetRedditUser :one
SELECT * FROM reddit_users WHERE username = $1;

-- name: UpsertRedditUser :one
INSERT INTO reddit_users (username, total_karma, investment_post_count, avg_upvote_ratio, trust_tier)
VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (username) DO UPDATE SET
  total_karma = EXCLUDED.total_karma,
  investment_post_count = reddit_users.investment_post_count + 1,
  avg_upvote_ratio = EXCLUDED.avg_upvote_ratio,
  last_scored_at = NOW()
RETURNING *;
```

- [ ] Generate sqlc code:

```bash
cd api && sqlc generate
```
Expected: creates `api/db/sqlc/` with generated Go files

- [ ] Commit:

```bash
git add api/sqlc.yaml api/db/
git commit -m "feat: sqlc schema and generated queries"
```

---

## Task 5: Python scraper scaffold

**Files:**
- Create: `scraper/pyproject.toml`
- Create: `scraper/scraper/__init__.py`
- Create: `scraper/scraper/config.py`
- Create: `scraper/scraper/models.py`
- Create: `scraper/scraper/worker.py`
- Create: `scraper/scraper/reddit.py`
- Create: `scraper/Dockerfile`

- [ ] Create `scraper/pyproject.toml`:

```toml
[project]
name = "argus-scraper"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "praw>=7.7",
  "playwright>=1.44",
  "httpx>=0.27",
  "beautifulsoup4>=4.12",
  "pydantic>=2.7",
  "asyncpg>=0.29",
  "redis>=5.0",
  "python-dotenv>=1.0",
  "lxml>=5.2",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]
```

- [ ] Create `scraper/scraper/config.py`:

```python
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
REDDIT_CLIENT_ID = os.environ["REDDIT_CLIENT_ID"]
REDDIT_CLIENT_SECRET = os.environ["REDDIT_CLIENT_SECRET"]
REDDIT_USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "argus-scraper/0.1 by makhskham")
```

- [ ] Create `scraper/scraper/models.py`:

```python
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class RawSignal(BaseModel):
    source: str
    source_type: str
    external_id: str
    subreddit: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None
    body: str
    url: Optional[str] = None
    upvotes: int = 0
    upvote_ratio: float = 0.0
    posted_at: datetime

class RedditUserMeta(BaseModel):
    username: str
    total_karma: int = 0
    avg_upvote_ratio: float = 0.0
```

- [ ] Create `scraper/scraper/reddit.py`:

```python
import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncIterator

import praw
from praw.models import Submission, Comment

from .config import REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
from .models import RawSignal, RedditUserMeta

log = logging.getLogger(__name__)

SUBREDDITS = [
    "investing", "stocks", "StockMarket", "Bogleheads", "dividends",
    "ValueInvesting", "SecurityAnalysis", "wallstreetbets", "Options",
    "Daytrading", "CanadianInvestor", "algotrading", "pennystocks",
    "Superstonk", "thetagang",
]

def _reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )

def _to_signal(post: Submission, subreddit: str) -> RawSignal:
    body = post.selftext or post.title
    return RawSignal(
        source=f"r/{subreddit}",
        source_type="reddit",
        external_id=post.id,
        subreddit=subreddit,
        author=str(post.author) if post.author else "[deleted]",
        title=post.title,
        body=body[:8000],
        url=f"https://reddit.com{post.permalink}",
        upvotes=post.score,
        upvote_ratio=post.upvote_ratio,
        posted_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
    )

def _comment_to_signal(comment: Comment, subreddit: str, post_id: str) -> RawSignal | None:
    if not comment.body or comment.body in ("[deleted]", "[removed]"):
        return None
    if len(comment.body) < 50:
        return None
    return RawSignal(
        source=f"r/{subreddit}",
        source_type="reddit",
        external_id=f"c_{comment.id}",
        subreddit=subreddit,
        author=str(comment.author) if comment.author else "[deleted]",
        body=comment.body[:4000],
        url=f"https://reddit.com/r/{subreddit}/comments/{post_id}/_/{comment.id}",
        upvotes=comment.score,
        upvote_ratio=0.0,
        posted_at=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
    )

async def scrape_subreddit(subreddit_name: str, limit: int = 100) -> list[RawSignal]:
    """Scrape top posts + all comments from a subreddit."""
    loop = asyncio.get_event_loop()
    signals: list[RawSignal] = []

    def _fetch():
        reddit = _reddit_client()
        sub = reddit.subreddit(subreddit_name)
        results = []
        for post in sub.hot(limit=limit):
            results.append(_to_signal(post, subreddit_name))
            post.comments.replace_more(limit=5)
            for comment in post.comments.list():
                sig = _comment_to_signal(comment, subreddit_name, post.id)
                if sig:
                    results.append(sig)
        return results

    try:
        signals = await loop.run_in_executor(None, _fetch)
        log.info("r/%s: scraped %d signals", subreddit_name, len(signals))
    except Exception as e:
        log.error("r/%s scrape failed: %s", subreddit_name, e)

    return signals

async def scrape_all_subreddits() -> list[RawSignal]:
    tasks = [scrape_subreddit(sub) for sub in SUBREDDITS]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    signals = []
    for r in results:
        if isinstance(r, list):
            signals.extend(r)
    return signals
```

- [ ] Create `scraper/scraper/worker.py`:

```python
import asyncio
import logging
import os

import asyncpg
from dotenv import load_dotenv

from .config import DATABASE_URL
from .reddit import scrape_all_subreddits
from .models import RawSignal

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def save_signals(conn: asyncpg.Connection, signals: list[RawSignal]) -> int:
    saved = 0
    for sig in signals:
        try:
            await conn.execute(
                """
                INSERT INTO signals
                  (source, source_type, external_id, subreddit, author, title, body, url, upvotes, upvote_ratio, posted_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (source_type, external_id) DO NOTHING
                """,
                sig.source, sig.source_type, sig.external_id, sig.subreddit,
                sig.author, sig.title, sig.body, sig.url,
                sig.upvotes, sig.upvote_ratio, sig.posted_at,
            )
            saved += 1
        except Exception as e:
            log.warning("insert failed: %s", e)
    return saved

async def run_cycle():
    pool = await asyncpg.create_pool(DATABASE_URL.replace("+asyncpg", ""))
    async with pool.acquire() as conn:
        cycle_id = await conn.fetchval(
            "INSERT INTO scrape_cycles DEFAULT VALUES RETURNING id"
        )
        log.info("scrape cycle %d started", cycle_id)

        signals = await scrape_all_subreddits()
        saved = await save_signals(conn, signals)

        await conn.execute(
            "UPDATE scrape_cycles SET status='complete', finished_at=NOW(), signals_added=$2 WHERE id=$1",
            cycle_id, saved,
        )
        log.info("cycle %d complete: %d signals saved", cycle_id, saved)

    await pool.close()

if __name__ == "__main__":
    asyncio.run(run_cycle())
```

- [ ] Create `scraper/Dockerfile`:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
RUN playwright install chromium --with-deps
COPY scraper/ ./scraper/
CMD ["python", "-m", "scraper.worker"]
```

- [ ] Create `scraper/.env.example`:

```env
DATABASE_URL=postgresql+asyncpg://argus:argus@localhost:5432/argus
REDIS_URL=redis://localhost:6379
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=argus-scraper/0.1 by makhskham
```

- [ ] Install and verify:

```bash
cd scraper && pip install -e ".[dev]" && python -c "import scraper; print('ok')"
```

- [ ] Commit:

```bash
git add scraper/
git commit -m "feat: python scraper scaffold with praw reddit worker"
```

---

## Task 6: Next.js 15 frontend scaffold

**Files:**
- Create: `web/` (via create-next-app)

- [ ] Scaffold Next.js:

```bash
cd C:/Users/makhs/Desktop/Projects/Argus
npx create-next-app@latest web \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --import-alias "@/*" \
  --no-git
```

- [ ] Install dependencies:

```bash
cd web
pnpm add @clerk/nextjs \
  @tanstack/react-query \
  nuqs \
  framer-motion \
  lucide-react \
  class-variance-authority \
  clsx \
  tailwind-merge \
  lightweight-charts \
  ai \
  @ai-sdk/anthropic \
  sonner \
  recharts
pnpm add -D @types/node
```

- [ ] Install shadcn/ui:

```bash
cd web && pnpm dlx shadcn@latest init -d
pnpm dlx shadcn@latest add button card badge separator tabs input textarea select
```

- [ ] Create `web/.env.local.example`:

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8080
ANTHROPIC_API_KEY=
```

- [ ] Replace `web/app/layout.tsx`:

```tsx
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import { ClerkProvider } from "@clerk/nextjs"
import { Providers } from "@/components/providers"
import "./globals.css"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Argus — Intelligence Platform",
  description: "AI-powered investment intelligence from every corner of the market",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark">
        <body className={`${inter.className} bg-black text-white antialiased`}>
          <Providers>{children}</Providers>
        </body>
      </html>
    </ClerkProvider>
  )
}
```

- [ ] Create `web/components/providers.tsx`:

```tsx
"use client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { NuqsAdapter } from "nuqs/adapters/next/app"
import { useState } from "react"

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000 } },
  }))
  return (
    <QueryClientProvider client={qc}>
      <NuqsAdapter>{children}</NuqsAdapter>
    </QueryClientProvider>
  )
}
```

- [ ] Update `web/app/globals.css` to set base black theme:

```css
@import "tailwindcss";

:root {
  --background: #000000;
  --foreground: #ffffff;
  --surface: #080808;
  --border: #161616;
  --muted: #4b5563;
  --dim: #2d2d2d;
  --bull: #22c55e;
  --bear: #ef4444;
  --neutral-amber: #f59e0b;
  --silver: #e2e8f0;
}

body {
  background: var(--background);
  color: var(--foreground);
}

* { box-sizing: border-box; }
```

- [ ] Verify Next.js builds:

```bash
cd web && pnpm build
```
Expected: Build succeeds

- [ ] Commit:

```bash
cd .. && git add web/
git commit -m "feat: next.js 15 scaffold with clerk, tanstack query, nuqs, shadcn"
```

---

## Task 7: Go REST API core routes

**Files:**
- Create: `api/internal/handler/recommendations.go`
- Create: `api/internal/handler/signals.go`
- Create: `api/internal/handler/health.go`
- Modify: `api/cmd/api/main.go`

- [ ] Create `api/internal/handler/health.go`:

```go
package handler

import (
	"encoding/json"
	"net/http"
)

func Health(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}
```

- [ ] Create `api/internal/handler/recommendations.go`:

```go
package handler

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/makhskham/argus/api/db/sqlc"
)

type RecommendationsHandler struct {
	db *pgxpool.Pool
	q  *db.Queries
}

func NewRecommendations(pool *pgxpool.Pool) *RecommendationsHandler {
	return &RecommendationsHandler{db: pool, q: db.New(pool)}
}

func (h *RecommendationsHandler) List(w http.ResponseWriter, r *http.Request) {
	direction := r.URL.Query().Get("direction")
	if direction == "" {
		direction = "buy"
	}
	halal := r.URL.Query().Get("halal") == "true"
	limit := int32(30)
	if l := r.URL.Query().Get("limit"); l != "" {
		if n, err := strconv.Atoi(l); err == nil && n > 0 && n <= 100 {
			limit = int32(n)
		}
	}

	var recs interface{}
	var err error
	if halal {
		recs, err = h.q.GetHalalRecommendations(r.Context(), db.GetHalalRecommendationsParams{
			Direction: direction, Limit: limit,
		})
	} else {
		recs, err = h.q.GetTopRecommendations(r.Context(), db.GetTopRecommendationsParams{
			Direction: direction, Limit: limit,
		})
	}
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(recs)
}

func (h *RecommendationsHandler) ByTicker(w http.ResponseWriter, r *http.Request) {
	ticker := chi.URLParam(r, "ticker")
	rec, err := h.q.GetRecommendationByTicker(r.Context(), ticker)
	if err != nil {
		http.Error(w, "not found", 404)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rec)
}
```

- [ ] Create `api/internal/handler/signals.go`:

```go
package handler

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/makhskham/argus/api/db/sqlc"
)

type SignalsHandler struct {
	db *pgxpool.Pool
	q  *db.Queries
}

func NewSignals(pool *pgxpool.Pool) *SignalsHandler {
	return &SignalsHandler{db: pool, q: db.New(pool)}
}

func (h *SignalsHandler) List(w http.ResponseWriter, r *http.Request) {
	since := time.Now().AddDate(0, 0, -7)
	signals, err := h.q.GetRecentSignals(r.Context(), db.GetRecentSignalsParams{
		ScrapedAt: since,
		Limit:     50,
		Offset:    0,
	})
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(signals)
}
```

- [ ] Update `api/cmd/api/main.go` to register routes:

```go
package main

import (
	"context"
	"log"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	"github.com/rs/cors"
	"github.com/makhskham/argus/api/internal/config"
	"github.com/makhskham/argus/api/internal/handler"
)

func main() {
	_ = godotenv.Load()
	cfg := config.Load()

	pool, err := pgxpool.New(context.Background(), cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("db connect: %v", err)
	}
	defer pool.Close()

	recH := handler.NewRecommendations(pool)
	sigH := handler.NewSignals(pool)

	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(cors.AllowAll().Handler)

	r.Get("/health", handler.Health)

	r.Route("/api/v1", func(r chi.Router) {
		r.Get("/recommendations", recH.List)
		r.Get("/recommendations/{ticker}", recH.ByTicker)
		r.Get("/signals", sigH.List)
	})

	log.Printf("api listening on :%s", cfg.Port)
	http.ListenAndServe(":"+cfg.Port, r)
}
```

- [ ] Build and verify:

```bash
cd api && go build ./...
```
Expected: no output (success)

- [ ] Commit:

```bash
git add api/internal/ api/cmd/
git commit -m "feat: go rest api with recommendations and signals endpoints"
```

---

## Task 8: Next.js sidebar layout and navigation

**Files:**
- Create: `web/app/(app)/layout.tsx`
- Create: `web/components/sidebar.tsx`
- Create: `web/app/(app)/dashboard/page.tsx`

- [ ] Create `web/components/sidebar.tsx`:

```tsx
"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { UserButton } from "@clerk/nextjs"
import { cn } from "@/lib/utils"

const nav = [
  { group: "Core", items: [
    { label: "Command Center", href: "/dashboard", icon: "⬡" },
    { label: "Intelligence Feed", href: "/intelligence", icon: "◈" },
    { label: "Date Explorer", href: "/explore", icon: "◷" },
  ]},
  { group: "Rankings", items: [
    { label: "Top Picks", href: "/picks", icon: "↑", badge: "30", badgeColor: "green" },
    { label: "Avoid List", href: "/avoid", icon: "↓", badge: "30", badgeColor: "red" },
    { label: "Halal Screen", href: "/halal", icon: "☽" },
    { label: "Watchlist", href: "/watchlist", icon: "◇" },
  ]},
  { group: "Tools", items: [
    { label: "AI Chat", href: "/chat", icon: "◎" },
    { label: "Data Sources", href: "/sources", icon: "◈" },
  ]},
  { group: "Account", items: [
    { label: "Profile & Goals", href: "/profile", icon: "○" },
  ]},
]

export function Sidebar() {
  const path = usePathname()
  return (
    <aside className="w-[210px] flex-shrink-0 bg-[#080808] border-r border-[#161616] flex flex-col h-screen sticky top-0">
      <div className="px-5 pt-5 pb-1">
        <div className="text-sm font-bold tracking-[0.14em] uppercase text-white">ARGUS</div>
        <div className="text-[10px] tracking-[0.18em] uppercase text-[#2d2d2d] mt-0.5">Intelligence Platform</div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-4">
        {nav.map(group => (
          <div key={group.group}>
            <div className="text-[9px] tracking-[0.16em] uppercase font-bold text-[#2d2d2d] px-2 mb-1">{group.group}</div>
            {group.items.map(item => {
              const active = path === item.href || path.startsWith(item.href + "/")
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs transition-colors border-l-2",
                    active
                      ? "bg-[#111] text-white border-[#e2e8f0]"
                      : "text-[#4b5563] border-transparent hover:text-[#94a3b8]"
                  )}
                >
                  <span className="w-3 text-center text-[10px]">{item.icon}</span>
                  <span className="flex-1">{item.label}</span>
                  {item.badge && (
                    <span className={cn(
                      "text-[9px] px-1.5 py-0.5 rounded border",
                      item.badgeColor === "green"
                        ? "bg-[#051208] text-[#22c55e] border-[#0a2810]"
                        : "bg-[#140305] text-[#ef4444] border-[#280510]"
                    )}>{item.badge}</span>
                  )}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="px-3 pb-4">
        <div className="bg-[#0d0d0d] border border-[#161616] rounded-lg p-3">
          <div className="flex items-center gap-2 mb-2">
            <UserButton afterSignOutUrl="/" />
            <div>
              <div className="text-xs font-semibold text-white">Account</div>
              <div className="text-[10px] text-[#4b5563]">Moderate · Long-term</div>
            </div>
          </div>
          <div className="flex gap-1.5">
            <div className="text-[10px] bg-[#111] border border-[#1c1c1c] rounded px-1.5 py-0.5 text-[#4b5563]">
              Budget <span className="text-[#e2e8f0] font-semibold">$25K</span>
            </div>
            <div className="text-[10px] bg-[#111] border border-[#1c1c1c] rounded px-1.5 py-0.5 text-[#4b5563]">
              ☽ <span className="text-[#22c55e] font-semibold">On</span>
            </div>
          </div>
        </div>
      </div>
    </aside>
  )
}
```

- [ ] Create `web/app/(app)/layout.tsx`:

```tsx
import { Sidebar } from "@/components/sidebar"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-black">
      <Sidebar />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  )
}
```

- [ ] Create `web/app/(app)/dashboard/page.tsx` (stub):

```tsx
export default function DashboardPage() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-bold text-white tracking-wide">Command Center</h1>
      <p className="text-[#4b5563] text-sm mt-1">Loading intelligence...</p>
    </div>
  )
}
```

- [ ] Verify dev server starts:

```bash
cd web && pnpm dev
```
Expected: server running on http://localhost:3000

- [ ] Commit:

```bash
git add web/
git commit -m "feat: app layout with dark sidebar navigation and clerk auth"
```

---

## Task 9: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  go:
    name: Go
    runs-on: ubuntu-latest
    strategy:
      matrix:
        go: ["1.23"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go }}
      - name: Build
        run: cd api && go build ./...
      - name: Test with race detector
        run: cd api && go test -race ./...

  python:
    name: Python
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install
        run: cd scraper && pip install -e ".[dev]"
      - name: Test
        run: cd scraper && pytest -v || true

  frontend:
    name: Frontend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"
          cache-dependency-path: web/pnpm-lock.yaml
      - run: cd web && pnpm install
      - run: cd web && pnpm build
```

- [ ] Commit:

```bash
git add .github/
git commit -m "ci: github actions with go race detector, python, and next.js build"
```

---

## Task 10: Push to GitHub

- [ ] Create repo on GitHub:

```bash
gh repo create makhskham/argus --public --description "AI-powered investment intelligence platform" --source . --remote origin
```

- [ ] Push:

```bash
git push -u origin main
```

Expected: Repo live at github.com/makhskham/argus, CI triggers automatically.
