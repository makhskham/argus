-- pgvector is supported on Supabase free tier
-- TimescaleDB is NOT on Supabase free tier - using regular indexed table instead
CREATE EXTENSION IF NOT EXISTS vector;

-- Reddit users / trust scoring
CREATE TABLE IF NOT EXISTS reddit_users (
  id                    BIGSERIAL PRIMARY KEY,
  username              TEXT NOT NULL UNIQUE,
  total_karma           BIGINT DEFAULT 0,
  investment_post_count INT DEFAULT 0,
  avg_upvote_ratio      FLOAT DEFAULT 0,
  trust_tier            TEXT NOT NULL DEFAULT 'unverified'
                          CHECK (trust_tier IN ('unverified','recognized','trusted','authority')),
  accuracy_score        FLOAT DEFAULT 0,
  calls_tracked         INT DEFAULT 0,
  last_scored_at        TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Raw scraped posts/comments from all sources
CREATE TABLE IF NOT EXISTS signals (
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

CREATE INDEX IF NOT EXISTS idx_signals_scraped_at ON signals(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_posted_at ON signals(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_subreddit ON signals(subreddit);

-- Claude-extracted analysis per signal
CREATE TABLE IF NOT EXISTS signal_analyses (
  id                   BIGSERIAL PRIMARY KEY,
  signal_id            BIGINT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
  tickers              TEXT[] NOT NULL DEFAULT '{}',
  sentiment            TEXT NOT NULL CHECK (sentiment IN ('bullish','bearish','neutral')),
  confidence           INT NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  key_quote            TEXT,
  is_prediction        BOOLEAN DEFAULT FALSE,
  prediction_direction TEXT,
  prediction_timeframe TEXT,
  is_niche_flagged     BOOLEAN DEFAULT FALSE,
  model_used           TEXT NOT NULL,
  analyzed_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analyses_tickers ON signal_analyses USING GIN(tickers);
CREATE INDEX IF NOT EXISTS idx_analyses_sentiment ON signal_analyses(sentiment);
CREATE INDEX IF NOT EXISTS idx_analyses_confidence ON signal_analyses(confidence DESC);

-- Voyage AI embeddings for semantic search (1024-dim for voyage-finance-2)
CREATE TABLE IF NOT EXISTS signal_embeddings (
  signal_id  BIGINT PRIMARY KEY REFERENCES signals(id) ON DELETE CASCADE,
  embedding  vector(1024) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw
  ON signal_embeddings USING hnsw (embedding vector_cosine_ops);

-- Per-ticker aggregated sentiment
CREATE TABLE IF NOT EXISTS ticker_sentiment (
  id           BIGSERIAL PRIMARY KEY,
  ticker       TEXT NOT NULL,
  period_start TIMESTAMPTZ NOT NULL,
  period_end   TIMESTAMPTZ NOT NULL,
  bull_pct     FLOAT NOT NULL DEFAULT 0,
  neutral_pct  FLOAT NOT NULL DEFAULT 0,
  bear_pct     FLOAT NOT NULL DEFAULT 0,
  confidence   INT NOT NULL DEFAULT 0,
  signal_count INT NOT NULL DEFAULT 0,
  source_count INT NOT NULL DEFAULT 0,
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(ticker, period_start, period_end)
);

-- Ranked recommendations (rebuilt each scrape cycle)
CREATE TABLE IF NOT EXISTS recommendations (
  id                 BIGSERIAL PRIMARY KEY,
  ticker             TEXT NOT NULL,
  company_name       TEXT,
  direction          TEXT NOT NULL CHECK (direction IN ('buy','avoid')),
  rank               INT NOT NULL,
  confidence         INT NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  bull_pct           FLOAT NOT NULL DEFAULT 0,
  neutral_pct        FLOAT NOT NULL DEFAULT 0,
  bear_pct           FLOAT NOT NULL DEFAULT 0,
  signal_count       INT NOT NULL DEFAULT 0,
  source_count       INT NOT NULL DEFAULT 0,
  ai_analysis        TEXT,
  price_target_base  NUMERIC(10,2),
  price_target_bull  NUMERIC(10,2),
  price_target_bear  NUMERIC(10,2),
  momentum_score     FLOAT DEFAULT 0,
  mention_velocity   FLOAT DEFAULT 0,
  first_mentioned_at TIMESTAMPTZ,
  stock_price        NUMERIC(10,2),
  market_cap_tier    TEXT DEFAULT 'unknown'
                       CHECK (market_cap_tier IN ('unknown','micro','small','mid','large','mega')),
  is_emerging        BOOLEAN DEFAULT FALSE,
  cycle_id           BIGINT NOT NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recommendations_direction_rank ON recommendations(direction, rank);
CREATE INDEX IF NOT EXISTS idx_recommendations_emerging ON recommendations(is_emerging, rank);
CREATE INDEX IF NOT EXISTS idx_recommendations_momentum ON recommendations(momentum_score DESC);

-- Scrape cycle tracking
CREATE TABLE IF NOT EXISTS scrape_cycles (
  id            BIGSERIAL PRIMARY KEY,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at   TIMESTAMPTZ,
  signals_added INT DEFAULT 0,
  status        TEXT NOT NULL DEFAULT 'running'
                  CHECK (status IN ('running','complete','failed'))
);

-- Halal / Shariah compliance cache (Zoya API)
CREATE TABLE IF NOT EXISTS halal_compliance (
  ticker                TEXT PRIMARY KEY,
  is_compliant          BOOLEAN,
  zoya_status           TEXT,
  debt_ratio            FLOAT,
  interest_income_ratio FLOAT,
  business_activity_ok  BOOLEAN,
  djimi_listed          BOOLEAN,
  last_checked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  next_check_at         TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '90 days'
);

-- User watchlists
CREATE TABLE IF NOT EXISTS watchlist (
  id            BIGSERIAL PRIMARY KEY,
  clerk_user_id TEXT NOT NULL,
  ticker        TEXT NOT NULL,
  added_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(clerk_user_id, ticker)
);

-- User investment profiles
CREATE TABLE IF NOT EXISTS user_profiles (
  clerk_user_id    TEXT PRIMARY KEY,
  budget           NUMERIC(14,2),
  per_stock_budget NUMERIC(14,2),
  risk_tolerance   TEXT CHECK (risk_tolerance IN ('conservative','moderate','aggressive')),
  investing_goal   TEXT CHECK (investing_goal IN ('retirement','short_term','passive_income','speculative')),
  halal_filter     BOOLEAN DEFAULT FALSE,
  excluded_tickers TEXT[] DEFAULT '{}',
  preferred_tiers  TEXT[] DEFAULT '{"micro","small","mid","large","mega"}',
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Stock price history (standard indexed table - TimescaleDB not needed for this scale)
CREATE TABLE IF NOT EXISTS price_history (
  ticker  TEXT NOT NULL,
  ts      TIMESTAMPTZ NOT NULL,
  open    NUMERIC(10,2),
  high    NUMERIC(10,2),
  low     NUMERIC(10,2),
  close   NUMERIC(10,2),
  volume  BIGINT,
  PRIMARY KEY (ticker, ts)
);

CREATE INDEX IF NOT EXISTS idx_price_history_ticker_ts ON price_history(ticker, ts DESC);

-- Mention velocity tracking (for hidden gem / emerging ticker detection)
CREATE TABLE IF NOT EXISTS ticker_velocity (
  ticker         TEXT NOT NULL,
  window_start   TIMESTAMPTZ NOT NULL,
  window_end     TIMESTAMPTZ NOT NULL,
  mention_count  INT NOT NULL DEFAULT 0,
  unique_sources INT NOT NULL DEFAULT 0,
  avg_upvotes    FLOAT DEFAULT 0,
  velocity_score FLOAT DEFAULT 0,
  PRIMARY KEY (ticker, window_start)
);

-- Emerging / hidden gem tickers
CREATE TABLE IF NOT EXISTS emerging_tickers (
  id                 BIGSERIAL PRIMARY KEY,
  ticker             TEXT NOT NULL UNIQUE,
  first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  initial_confidence INT DEFAULT 0,
  source_subreddit   TEXT,
  first_mention_body TEXT,
  graduation_score   FLOAT DEFAULT 0,
  graduated_at       TIMESTAMPTZ,
  is_graduated       BOOLEAN DEFAULT FALSE
);
