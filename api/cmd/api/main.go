package main

import (
	"context"
	"log"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/joho/godotenv"
	"github.com/makhskham/argus/api/internal/config"
	"github.com/makhskham/argus/api/internal/handler"
	"github.com/rs/cors"
)

func main() {
	_ = godotenv.Load()
	cfg := config.Load()

	pool, err := pgxpool.New(context.Background(), cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("db connect: %v", err)
	}
	defer pool.Close()

	recH := handler.NewRecommendations(pool)
	sigH := handler.NewSignals(pool)

	r := chi.NewRouter()
	r.Use(middleware.Logger)
	r.Use(middleware.Recoverer)
	r.Use(cors.AllowAll().Handler)

	r.Get("/health", handler.Health)

	r.Route("/api/v1", func(r chi.Router) {
		r.Get("/recommendations", recH.List)
		r.Get("/recommendations/{ticker}", recH.ByTicker)
		r.Get("/signals", sigH.List)
	})

	log.Printf("api listening on :%s", cfg.Port)
	http.ListenAndServe(":"+cfg.Port, r)
}
