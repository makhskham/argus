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

-- Per-ticker aggregated sentiment
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

-- User watchlist
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
