-- Add momentum and price tracking to recommendations
ALTER TABLE recommendations
  ADD COLUMN IF NOT EXISTS momentum_score     FLOAT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS mention_velocity   FLOAT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS first_mentioned_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS stock_price        NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS market_cap_tier    TEXT DEFAULT 'unknown'
    CHECK (market_cap_tier IN ('unknown','micro','small','mid','large','mega')),
  ADD COLUMN IF NOT EXISTS is_emerging        BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_recommendations_emerging ON recommendations(is_emerging, rank);
CREATE INDEX IF NOT EXISTS idx_recommendations_momentum ON recommendations(momentum_score DESC);

-- Add per-stock budget to user profiles
ALTER TABLE user_profiles
  ADD COLUMN IF NOT EXISTS per_stock_budget   NUMERIC(14,2),
  ADD COLUMN IF NOT EXISTS preferred_tiers    TEXT[] DEFAULT '{"micro","small","mid","large","mega"}';

-- Mention velocity tracking (how fast a ticker is being talked about)
CREATE TABLE IF NOT EXISTS ticker_velocity (
  ticker          TEXT NOT NULL,
  window_start    TIMESTAMPTZ NOT NULL,
  window_end      TIMESTAMPTZ NOT NULL,
  mention_count   INT NOT NULL DEFAULT 0,
  unique_sources  INT NOT NULL DEFAULT 0,
  avg_upvotes     FLOAT DEFAULT 0,
  velocity_score  FLOAT DEFAULT 0,
  PRIMARY KEY (ticker, window_start)
);

-- Emerging ticker alerts (first time a ticker appears with decent signal strength)
CREATE TABLE IF NOT EXISTS emerging_tickers (
  id              BIGSERIAL PRIMARY KEY,
  ticker          TEXT NOT NULL UNIQUE,
  first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  initial_confidence INT DEFAULT 0,
  source_subreddit   TEXT,
  first_mention_body TEXT,
  graduation_score   FLOAT DEFAULT 0,
  graduated_at    TIMESTAMPTZ,
  is_graduated    BOOLEAN DEFAULT FALSE
);
