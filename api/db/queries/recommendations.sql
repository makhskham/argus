-- name: InsertRecommendation :one
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

-- name: CreateScrapeCycle :one
INSERT INTO scrape_cycles DEFAULT VALUES RETURNING *;

-- name: CompleteScrapeCycle :one
UPDATE scrape_cycles SET status = 'complete', finished_at = NOW(), signals_added = $2
WHERE id = $1 RETURNING *;
