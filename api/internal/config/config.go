// Package config loads environment-based configuration.
package config

import (
	"fmt"
	"os"
	"strconv"
)

// Config holds all server configuration.
type Config struct {
	// Server
	Port    int
	BaseURL string // e.g. "http://localhost:8080" — used for OAuth callback

	// Database
	DatabaseURL string

	// GitHub OAuth (App)
	GitHubClientID     string
	GitHubClientSecret string

	// Session
	SessionSecret string // 32+ byte key for cookie encryption / JWT signing

	// Encryption
	EncryptionKey string // 32-byte hex key for AES-256-GCM token encryption
}

// Load reads configuration from environment variables.
func Load() (*Config, error) {
	port := 8080
	if p := os.Getenv("PORT"); p != "" {
		var err error
		port, err = strconv.Atoi(p)
		if err != nil {
			return nil, fmt.Errorf("invalid PORT: %w", err)
		}
	}

	baseURL := os.Getenv("BASE_URL")
	if baseURL == "" {
		baseURL = fmt.Sprintf("http://localhost:%d", port)
	}

	dbURL := os.Getenv("DATABASE_URL")
	if dbURL == "" {
		dbURL = "postgres://specmap:specmap_dev@localhost:5432/specmap?sslmode=disable"
	}

	cfg := &Config{
		Port:               port,
		BaseURL:            baseURL,
		DatabaseURL:        dbURL,
		GitHubClientID:     os.Getenv("GITHUB_CLIENT_ID"),
		GitHubClientSecret: os.Getenv("GITHUB_CLIENT_SECRET"),
		SessionSecret:      os.Getenv("SESSION_SECRET"),
		EncryptionKey:      os.Getenv("ENCRYPTION_KEY"),
	}

	return cfg, nil
}
