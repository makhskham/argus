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
