// Package server sets up HTTP routing and middleware.
package server

import (
	"net/http"

	"github.com/specmap/specmap/api/internal/auth"
	"github.com/specmap/specmap/api/internal/config"
	"github.com/specmap/specmap/api/internal/store"
)

// Server holds dependencies and exposes the HTTP handler.
type Server struct {
	cfg   *config.Config
	store *store.Store
	oauth *auth.OAuthConfig
	mux   *http.ServeMux
}

// New creates a Server and registers all routes.
func New(cfg *config.Config, st *store.Store) *Server {
	s := &Server{
		cfg:   cfg,
		store: st,
		oauth: &auth.OAuthConfig{
			ClientID:     cfg.GitHubClientID,
			ClientSecret: cfg.GitHubClientSecret,
			BaseURL:      cfg.BaseURL,
		},
		mux: http.NewServeMux(),
	}
	s.routes()
	return s
}

// Handler returns the server's top-level HTTP handler with middleware.
func (s *Server) Handler() http.Handler {
	return logging(s.mux)
}

func (s *Server) routes() {
	// Health check (no auth).
	s.mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	// Auth endpoints (no auth required).
	s.mux.HandleFunc("GET /api/v1/auth/login", s.handleLogin)
	s.mux.HandleFunc("GET /api/v1/auth/callback", s.handleCallback)

	// Auth endpoints (require session).
	authed := s.requireAuth
	s.mux.Handle("POST /api/v1/auth/logout", authed(http.HandlerFunc(s.handleLogout)))
	s.mux.Handle("GET /api/v1/auth/me", authed(http.HandlerFunc(s.handleMe)))

	// Repos (require session).
	s.mux.Handle("GET /api/v1/repos", authed(http.HandlerFunc(s.handleListRepos)))
	s.mux.Handle("GET /api/v1/repos/{owner}/{repo}", authed(http.HandlerFunc(s.handleGetRepo)))

	// Pull requests (require session).
	s.mux.Handle("GET /api/v1/repos/{owner}/{repo}/pulls", authed(http.HandlerFunc(s.handleListPulls)))
	s.mux.Handle("GET /api/v1/repos/{owner}/{repo}/pulls/{number}", authed(http.HandlerFunc(s.handleGetPull)))
	s.mux.Handle("GET /api/v1/repos/{owner}/{repo}/pulls/{number}/files", authed(http.HandlerFunc(s.handleGetPullFiles)))
}
