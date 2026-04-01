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
	BaseURL string // e.g. "https://localhost:8080" — used for OAuth callback

	// Database
	DatabaseURL string

	// GitHub OAuth (App)
	GitHubClientID     string
	GitHubClientSecret string

	// Session
	SessionSecret string // 32+ byte key for cookie encryption / JWT signing

	// Encryption
	EncryptionKey string // 32-byte hex key for AES-256-GCM token encryption

	// GitHub App (optional — enables app-level auth and webhooks)
	GitHubAppID          int64  // GITHUB_APP_ID
	GitHubPrivateKeyPath string // GITHUB_PRIVATE_KEY_PATH (path to .pem file)
	GitHubWebhookSecret  string // GITHUB_WEBHOOK_SECRET

	// CORS
	CORSOrigin string // allowed origin for CORS (e.g. "http://localhost:5173")

	// Frontend redirect target after OAuth login (defaults to CORSOrigin, then BaseURL)
	FrontendURL string

	// TLS (local dev with mkcert)
	TLSCert string // path to TLS certificate file
	TLSKey  string // path to TLS private key file

	// Version (set by main, not from env)
	Version string
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

	var appID int64
	if id := os.Getenv("GITHUB_APP_ID"); id != "" {
		var err error
		appID, err = strconv.ParseInt(id, 10, 64)
		if err != nil {
			return nil, fmt.Errorf("invalid GITHUB_APP_ID: %w", err)
		}
	}

	cfg := &Config{
		Port:                 port,
		BaseURL:              baseURL,
		DatabaseURL:          dbURL,
		GitHubClientID:       os.Getenv("GITHUB_CLIENT_ID"),
		GitHubClientSecret:   os.Getenv("GITHUB_CLIENT_SECRET"),
		SessionSecret:        os.Getenv("SESSION_SECRET"),
		EncryptionKey:        os.Getenv("ENCRYPTION_KEY"),
		GitHubAppID:          appID,
		GitHubPrivateKeyPath: os.Getenv("GITHUB_PRIVATE_KEY_PATH"),
		GitHubWebhookSecret:  os.Getenv("GITHUB_WEBHOOK_SECRET"),
		CORSOrigin:           os.Getenv("CORS_ORIGIN"),
		TLSCert:              os.Getenv("TLS_CERT"),
		TLSKey:               os.Getenv("TLS_KEY"),
	}

	// Post-login redirect: prefer FRONTEND_URL, then CORS_ORIGIN, then BASE_URL.
	cfg.FrontendURL = os.Getenv("FRONTEND_URL")
	if cfg.FrontendURL == "" {
		cfg.FrontendURL = cfg.CORSOrigin
	}
	if cfg.FrontendURL == "" {
		cfg.FrontendURL = cfg.BaseURL
	}

	return cfg, nil
}
