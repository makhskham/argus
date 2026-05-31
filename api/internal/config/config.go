package config

import (
	"os"
)

type Config struct {
	DatabaseURL  string
	RedisURL     string
	AnthropicKey string
	VoyageKey    string
	PolygonKey   string
	ZoyaKey      string
	Port         string
}

func Load() Config {
	return Config{
		DatabaseURL:  mustEnv("DATABASE_URL"),
		RedisURL:     getEnv("REDIS_URL", "redis://localhost:6379"),
		AnthropicKey: mustEnv("ANTHROPIC_API_KEY"),
		VoyageKey:    mustEnv("VOYAGE_API_KEY"),
		PolygonKey:   mustEnv("POLYGON_API_KEY"),
		ZoyaKey:      getEnv("ZOYA_API_KEY", ""),
		Port:         getEnv("PORT", "8080"),
	}
}

func mustEnv(key string) string {
	v := os.Getenv(key)
	if v == "" {
		panic("missing required env var: " + key)
	}
	return v
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
