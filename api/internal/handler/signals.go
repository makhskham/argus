package handler

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

type SignalsHandler struct {
	db *pgxpool.Pool
}

func NewSignals(pool *pgxpool.Pool) *SignalsHandler {
	return &SignalsHandler{db: pool}
}

func (h *SignalsHandler) List(w http.ResponseWriter, r *http.Request) {
	since := time.Now().AddDate(0, 0, -7)
	if s := r.URL.Query().Get("since"); s != "" {
		if t, err := time.Parse(time.RFC3339, s); err == nil {
			since = t
		}
	}

	ticker := r.URL.Query().Get("ticker")
	sentiment := r.URL.Query().Get("sentiment")
	halal := r.URL.Query().Get("halal") == "true"

	query := `
		SELECT s.id, s.source, s.source_type, s.subreddit, s.author, s.title,
		       s.body, s.url, s.upvotes, s.upvote_ratio, s.posted_at,
		       sa.tickers, sa.sentiment, sa.confidence, sa.key_quote, sa.is_niche_flagged,
		       ru.trust_tier,
		       h.is_compliant AS halal_compliant
		FROM signals s
		LEFT JOIN signal_analyses sa ON sa.signal_id = s.id
		LEFT JOIN reddit_users ru ON ru.id = s.reddit_user_id
		LEFT JOIN halal_compliance h ON h.ticker = ANY(sa.tickers)
		WHERE s.scraped_at >= $1
		  AND ($2 = '' OR $2 = ANY(sa.tickers))
		  AND ($3 = '' OR sa.sentiment = $3)
		  AND ($4 = false OR h.is_compliant = true)
		ORDER BY sa.confidence DESC NULLS LAST, s.upvotes DESC
		LIMIT 50
	`

	rows, err := h.db.Query(r.Context(), query, since, ticker, sentiment, halal)
	if err != nil {
		http.Error(w, "query failed", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	type Row struct {
		ID             int64     `json:"id"`
		Source         string    `json:"source"`
		SourceType     string    `json:"source_type"`
		Subreddit      *string   `json:"subreddit"`
		Author         *string   `json:"author"`
		Title          *string   `json:"title"`
		Body           string    `json:"body"`
		URL            *string   `json:"url"`
		Upvotes        int       `json:"upvotes"`
		UpvoteRatio    float64   `json:"upvote_ratio"`
		PostedAt       time.Time `json:"posted_at"`
		Tickers        []string  `json:"tickers"`
		Sentiment      *string   `json:"sentiment"`
		Confidence     *int      `json:"confidence"`
		KeyQuote       *string   `json:"key_quote"`
		IsNicheFlagged *bool     `json:"is_niche_flagged"`
		TrustTier      *string   `json:"trust_tier"`
		HalalCompliant *bool     `json:"halal_compliant"`
	}

	var sigs []Row
	for rows.Next() {
		var row Row
		if err := rows.Scan(
			&row.ID, &row.Source, &row.SourceType, &row.Subreddit, &row.Author, &row.Title,
			&row.Body, &row.URL, &row.Upvotes, &row.UpvoteRatio, &row.PostedAt,
			&row.Tickers, &row.Sentiment, &row.Confidence, &row.KeyQuote, &row.IsNicheFlagged,
			&row.TrustTier, &row.HalalCompliant,
		); err != nil {
			continue
		}
		sigs = append(sigs, row)
	}
	if sigs == nil {
		sigs = []Row{}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(sigs)
}
