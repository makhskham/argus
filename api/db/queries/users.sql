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
