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
	limit := 30
	if l := r.URL.Query().Get("limit"); l != "" {
		if n, err := strconv.Atoi(l); err == nil && n > 0 && n <= 100 {
			limit = n
		}
	}

	rows, err := h.db.Query(r.Context(), `
		SELECT r.id, r.ticker, r.company_name, r.direction, r.rank, r.confidence,
		       r.bull_pct, r.neutral_pct, r.bear_pct, r.signal_count, r.source_count,
		       r.ai_analysis, r.price_target_base, r.price_target_bull, r.price_target_bear,
		       h.is_compliant AS halal_compliant
		FROM recommendations r
		LEFT JOIN halal_compliance h ON h.ticker = r.ticker
		WHERE r.direction = $1
		  AND r.cycle_id = (SELECT COALESCE(MAX(id),0) FROM scrape_cycles WHERE status = 'complete')
		  AND ($2 = false OR h.is_compliant = true)
		ORDER BY r.rank
		LIMIT $3
	`, direction, halal, limit)
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
		SignalCount     int      `json:"signal_count"`
		SourceCount     int      `json:"source_count"`
		AIAnalysis      *string  `json:"ai_analysis"`
		PriceTargetBase *float64 `json:"price_target_base"`
		PriceTargetBull *float64 `json:"price_target_bull"`
		PriceTargetBear *float64 `json:"price_target_bear"`
		HalalCompliant  *bool    `json:"halal_compliant"`
	}

	var recs []Row
	for rows.Next() {
		var rec Row
		if err := rows.Scan(
			&rec.ID, &rec.Ticker, &rec.CompanyName, &rec.Direction, &rec.Rank, &rec.Confidence,
			&rec.BullPct, &rec.NeutralPct, &rec.BearPct, &rec.SignalCount, &rec.SourceCount,
			&rec.AIAnalysis, &rec.PriceTargetBase, &rec.PriceTargetBull, &rec.PriceTargetBear,
			&rec.HalalCompliant,
		); err != nil {
			continue
		}
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
		HalalCompliant  *bool    `json:"halal_compliant"`
		DebtRatio       *float64 `json:"debt_ratio"`
	}

	var rec Row
	err := h.db.QueryRow(r.Context(), `
		SELECT r.ticker, r.company_name, r.direction, r.rank, r.confidence,
		       r.bull_pct, r.neutral_pct, r.bear_pct, r.ai_analysis,
		       r.price_target_base, r.price_target_bull, r.price_target_bear,
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
		&rec.HalalCompliant, &rec.DebtRatio,
	)
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rec)
}
