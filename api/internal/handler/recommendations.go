package handler

import (
	"encoding/json"
	"net/http"
	"strconv"

	"github.com/go-chi/chi/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type RecommendationsHandler struct {
	db *pgxpool.Pool
}

func NewRecommendations(pool *pgxpool.Pool) *RecommendationsHandler {
	return &RecommendationsHandler{db: pool}
}

func (h *RecommendationsHandler) List(w http.ResponseWriter, r *http.Request) {
	direction := r.URL.Query().Get("direction")
	if direction == "" {
		direction = "buy"
	}
	if direction != "buy" && direction != "avoid" {
		http.Error(w, "direction must be buy or avoid", http.StatusBadRequest)
		return
	}

	halal := r.URL.Query().Get("halal") == "true"
	emerging := r.URL.Query().Get("emerging") == "true"

	limit := 30
	if l := r.URL.Query().Get("limit"); l != "" {
		if n, err := strconv.Atoi(l); err == nil && n > 0 && n <= 100 {
			limit = n
		}
	}

	// Optional budget filter: max price per share
	var maxPrice *float64
	if mp := r.URL.Query().Get("max_price"); mp != "" {
		if v, err := strconv.ParseFloat(mp, 64); err == nil && v > 0 {
			maxPrice = &v
		}
	}

	// Cap tiers filter (comma-separated: micro,small,mid,large,mega)
	capTiers := r.URL.Query().Get("cap_tiers")

	query := `
		SELECT r.id, r.ticker, r.company_name, r.direction, r.rank, r.confidence,
		       r.bull_pct, r.neutral_pct, r.bear_pct, r.signal_count, r.source_count,
		       r.ai_analysis, r.price_target_base, r.price_target_bull, r.price_target_bear,
		       r.momentum_score, r.mention_velocity, r.stock_price, r.market_cap_tier,
		       r.is_emerging, r.first_mentioned_at,
		       h.is_compliant AS halal_compliant
		FROM recommendations r
		LEFT JOIN halal_compliance h ON h.ticker = r.ticker
		WHERE r.direction = $1
		  AND r.cycle_id = (SELECT COALESCE(MAX(id),0) FROM scrape_cycles WHERE status = 'complete')
		  AND ($2 = false OR h.is_compliant = true)
		  AND ($3 = false OR r.is_emerging = true)
		  AND ($4::numeric IS NULL OR r.stock_price IS NULL OR r.stock_price <= $4)
		  AND ($5 = '' OR r.market_cap_tier = ANY(string_to_array($5, ',')))
		ORDER BY
		  CASE WHEN $3 = true THEN r.momentum_score ELSE r.confidence::float END DESC
		LIMIT $6
	`

	var maxPriceVal interface{} = nil
	if maxPrice != nil {
		maxPriceVal = *maxPrice
	}

	rows, err := h.db.Query(r.Context(), query,
		direction, halal, emerging, maxPriceVal, capTiers, limit)
	if err != nil {
		http.Error(w, "query failed", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type Row struct {
		ID              int64    `json:"id"`
		Ticker          string   `json:"ticker"`
		CompanyName     *string  `json:"company_name"`
		Direction       string   `json:"direction"`
		Rank            int      `json:"rank"`
		Confidence      int      `json:"confidence"`
		BullPct         float64  `json:"bull_pct"`
		NeutralPct      float64  `json:"neutral_pct"`
		BearPct         float64  `json:"bear_pct"`
		SignalCount      int      `json:"signal_count"`
		SourceCount      int      `json:"source_count"`
		AIAnalysis      *string  `json:"ai_analysis"`
		PriceTargetBase *float64 `json:"price_target_base"`
		PriceTargetBull *float64 `json:"price_target_bull"`
		PriceTargetBear *float64 `json:"price_target_bear"`
		MomentumScore   *float64 `json:"momentum_score"`
		MentionVelocity *float64 `json:"mention_velocity"`
		StockPrice      *float64 `json:"stock_price"`
		MarketCapTier   *string  `json:"market_cap_tier"`
		IsEmerging      *bool    `json:"is_emerging"`
		FirstMentioned  *string  `json:"first_mentioned_at"`
		HalalCompliant  *bool    `json:"halal_compliant"`
	}

	var recs []Row
	for rows.Next() {
		var rec Row
		var firstMentioned *interface{}
		if err := rows.Scan(
			&rec.ID, &rec.Ticker, &rec.CompanyName, &rec.Direction, &rec.Rank, &rec.Confidence,
			&rec.BullPct, &rec.NeutralPct, &rec.BearPct, &rec.SignalCount, &rec.SourceCount,
			&rec.AIAnalysis, &rec.PriceTargetBase, &rec.PriceTargetBull, &rec.PriceTargetBear,
			&rec.MomentumScore, &rec.MentionVelocity, &rec.StockPrice, &rec.MarketCapTier,
			&rec.IsEmerging, &rec.FirstMentioned,
			&rec.HalalCompliant,
		); err != nil {
			continue
		}
		_ = firstMentioned
		recs = append(recs, rec)
	}
	if recs == nil {
		recs = []Row{}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(recs)
}

func (h *RecommendationsHandler) ByTicker(w http.ResponseWriter, r *http.Request) {
	ticker := chi.URLParam(r, "ticker")

	type Row struct {
		Ticker          string   `json:"ticker"`
		CompanyName     *string  `json:"company_name"`
		Direction       string   `json:"direction"`
		Rank            int      `json:"rank"`
		Confidence      int      `json:"confidence"`
		BullPct         float64  `json:"bull_pct"`
		NeutralPct      float64  `json:"neutral_pct"`
		BearPct         float64  `json:"bear_pct"`
		AIAnalysis      *string  `json:"ai_analysis"`
		PriceTargetBase *float64 `json:"price_target_base"`
		PriceTargetBull *float64 `json:"price_target_bull"`
		PriceTargetBear *float64 `json:"price_target_bear"`
		MomentumScore   *float64 `json:"momentum_score"`
		StockPrice      *float64 `json:"stock_price"`
		MarketCapTier   *string  `json:"market_cap_tier"`
		IsEmerging      *bool    `json:"is_emerging"`
		HalalCompliant  *bool    `json:"halal_compliant"`
		DebtRatio       *float64 `json:"debt_ratio"`
	}

	var rec Row
	err := h.db.QueryRow(r.Context(), `
		SELECT r.ticker, r.company_name, r.direction, r.rank, r.confidence,
		       r.bull_pct, r.neutral_pct, r.bear_pct, r.ai_analysis,
		       r.price_target_base, r.price_target_bull, r.price_target_bear,
		       r.momentum_score, r.stock_price, r.market_cap_tier, r.is_emerging,
		       h.is_compliant, h.debt_ratio
		FROM recommendations r
		LEFT JOIN halal_compliance h ON h.ticker = r.ticker
		WHERE r.ticker = $1
		  AND r.cycle_id = (SELECT COALESCE(MAX(id),0) FROM scrape_cycles WHERE status = 'complete')
		LIMIT 1
	`, ticker).Scan(
		&rec.Ticker, &rec.CompanyName, &rec.Direction, &rec.Rank, &rec.Confidence,
		&rec.BullPct, &rec.NeutralPct, &rec.BearPct, &rec.AIAnalysis,
		&rec.PriceTargetBase, &rec.PriceTargetBull, &rec.PriceTargetBear,
		&rec.MomentumScore, &rec.StockPrice, &rec.MarketCapTier, &rec.IsEmerging,
		&rec.HalalCompliant, &rec.DebtRatio,
	)
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rec)
}

func (h *RecommendationsHandler) Emerging(w http.ResponseWriter, r *http.Request) {
	halal := r.URL.Query().Get("halal") == "true"
	limit := 20
	if l := r.URL.Query().Get("limit"); l != "" {
		if n, err := strconv.Atoi(l); err == nil && n > 0 {
			limit = n
		}
	}

	rows, err := h.db.Query(r.Context(), `
		SELECT e.ticker, e.first_seen_at, e.initial_confidence,
		       e.source_subreddit, e.first_mention_body, e.graduation_score,
		       h.is_compliant AS halal_compliant,
		       r.stock_price, r.market_cap_tier, r.momentum_score, r.confidence,
		       r.bull_pct, r.signal_count
		FROM emerging_tickers e
		LEFT JOIN halal_compliance h ON h.ticker = e.ticker
		LEFT JOIN recommendations r ON r.ticker = e.ticker
		  AND r.cycle_id = (SELECT COALESCE(MAX(id),0) FROM scrape_cycles WHERE status = 'complete')
		WHERE ($1 = false OR h.is_compliant = true)
		  AND e.is_graduated = false
		ORDER BY e.graduation_score DESC, e.first_seen_at DESC
		LIMIT $2
	`, halal, limit)
	if err != nil {
		http.Error(w, "query failed", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type EmergingRow struct {
		Ticker           string   `json:"ticker"`
		FirstSeenAt      string   `json:"first_seen_at"`
		InitialConfidence int     `json:"initial_confidence"`
		SourceSubreddit  *string  `json:"source_subreddit"`
		FirstMentionBody *string  `json:"first_mention_body"`
		GraduationScore  float64  `json:"graduation_score"`
		HalalCompliant   *bool    `json:"halal_compliant"`
		StockPrice       *float64 `json:"stock_price"`
		MarketCapTier    *string  `json:"market_cap_tier"`
		MomentumScore    *float64 `json:"momentum_score"`
		Confidence       *int     `json:"confidence"`
		BullPct          *float64 `json:"bull_pct"`
		SignalCount       *int    `json:"signal_count"`
	}

	var rows2 []EmergingRow
	for rows.Next() {
		var row EmergingRow
		var firstSeen interface{}
		if err := rows.Scan(
			&row.Ticker, &firstSeen, &row.InitialConfidence,
			&row.SourceSubreddit, &row.FirstMentionBody, &row.GraduationScore,
			&row.HalalCompliant, &row.StockPrice, &row.MarketCapTier,
			&row.MomentumScore, &row.Confidence, &row.BullPct, &row.SignalCount,
		); err != nil {
			continue
		}
		if firstSeen != nil {
			row.FirstSeenAt = "recent"
		}
		rows2 = append(rows2, row)
	}
	if rows2 == nil {
		rows2 = []EmergingRow{}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rows2)
}
