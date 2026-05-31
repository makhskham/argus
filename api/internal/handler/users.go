package handler

import (
	"encoding/json"
	"net/http"

	"github.com/jackc/pgx/v5/pgxpool"
)

type UsersHandler struct {
	db *pgxpool.Pool
}

func NewUsers(pool *pgxpool.Pool) *UsersHandler {
	return &UsersHandler{db: pool}
}

type UserProfileRequest struct {
	ClerkUserID     string   `json:"clerk_user_id"`
	Budget          *float64 `json:"budget"`
	PerStockBudget  *float64 `json:"per_stock_budget"`
	RiskTolerance   *string  `json:"risk_tolerance"`
	InvestingGoal   *string  `json:"investing_goal"`
	HalalFilter     bool     `json:"halal_filter"`
	ExcludedTickers []string `json:"excluded_tickers"`
	PreferredTiers  []string `json:"preferred_tiers"`
}

func (h *UsersHandler) UpsertProfile(w http.ResponseWriter, r *http.Request) {
	var req UserProfileRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid json", http.StatusBadRequest)
		return
	}
	if req.ClerkUserID == "" {
		http.Error(w, "clerk_user_id required", http.StatusBadRequest)
		return
	}

	excluded := req.ExcludedTickers
	if excluded == nil {
		excluded = []string{}
	}
	tiers := req.PreferredTiers
	if tiers == nil {
		tiers = []string{"micro", "small", "mid", "large", "mega"}
	}

	_, err := h.db.Exec(r.Context(), `
		INSERT INTO user_profiles (clerk_user_id, budget, per_stock_budget, risk_tolerance, investing_goal, halal_filter, excluded_tickers, preferred_tiers)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (clerk_user_id) DO UPDATE SET
		  budget = EXCLUDED.budget,
		  per_stock_budget = EXCLUDED.per_stock_budget,
		  risk_tolerance = EXCLUDED.risk_tolerance,
		  investing_goal = EXCLUDED.investing_goal,
		  halal_filter = EXCLUDED.halal_filter,
		  excluded_tickers = EXCLUDED.excluded_tickers,
		  preferred_tiers = EXCLUDED.preferred_tiers,
		  updated_at = NOW()
	`, req.ClerkUserID, req.Budget, req.PerStockBudget, req.RiskTolerance,
		req.InvestingGoal, req.HalalFilter, excluded, tiers)
	if err != nil {
		http.Error(w, "db error: "+err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func (h *UsersHandler) GetProfile(w http.ResponseWriter, r *http.Request) {
	clerkID := r.URL.Query().Get("clerk_user_id")
	if clerkID == "" {
		http.Error(w, "clerk_user_id required", http.StatusBadRequest)
		return
	}

	type Profile struct {
		ClerkUserID     string   `json:"clerk_user_id"`
		Budget          *float64 `json:"budget"`
		PerStockBudget  *float64 `json:"per_stock_budget"`
		RiskTolerance   *string  `json:"risk_tolerance"`
		InvestingGoal   *string  `json:"investing_goal"`
		HalalFilter     bool     `json:"halal_filter"`
		ExcludedTickers []string `json:"excluded_tickers"`
		PreferredTiers  []string `json:"preferred_tiers"`
	}

	var p Profile
	err := h.db.QueryRow(r.Context(), `
		SELECT clerk_user_id, budget, per_stock_budget, risk_tolerance, investing_goal,
		       halal_filter, excluded_tickers, preferred_tiers
		FROM user_profiles WHERE clerk_user_id = $1
	`, clerkID).Scan(
		&p.ClerkUserID, &p.Budget, &p.PerStockBudget, &p.RiskTolerance, &p.InvestingGoal,
		&p.HalalFilter, &p.ExcludedTickers, &p.PreferredTiers,
	)
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(p)
}
