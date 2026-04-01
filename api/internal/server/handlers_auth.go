package server

import (
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/specmap/specmap/api/internal/auth"
	"github.com/specmap/specmap/api/internal/github"
	"github.com/specmap/specmap/api/internal/models"
)

// handleLogin redirects the user to GitHub's OAuth authorization page.
func (s *Server) handleLogin(w http.ResponseWriter, r *http.Request) {
	loginURL, cookie, err := s.oauth.LoginURL()
	if err != nil {
		slog.Error("generating login URL", "error", err)
		http.Error(w, `{"error":"internal error"}`, http.StatusInternalServerError)
		return
	}

	http.SetCookie(w, cookie)
	http.Redirect(w, r, loginURL, http.StatusTemporaryRedirect)
}

// handleCallback handles the OAuth callback from GitHub.
func (s *Server) handleCallback(w http.ResponseWriter, r *http.Request) {
	// GitHub App post-installation redirect: setup_action is present but state is not
	// (this isn't a user-initiated OAuth flow). The installation is already complete —
	// redirect to the frontend where the user can log in normally.
	if r.URL.Query().Get("setup_action") != "" && r.URL.Query().Get("state") == "" {
		slog.Info("GitHub App installation redirect",
			"setup_action", r.URL.Query().Get("setup_action"),
			"installation_id", r.URL.Query().Get("installation_id"),
		)
		http.Redirect(w, r, s.cfg.FrontendURL+"/", http.StatusTemporaryRedirect)
		return
	}

	// Verify state matches cookie (CSRF protection).
	state := r.URL.Query().Get("state")
	cookieState, err := auth.GetStateCookie(r)
	if err != nil || state == "" || state != cookieState {
		http.Error(w, `{"error":"invalid state"}`, http.StatusBadRequest)
		return
	}

	code := r.URL.Query().Get("code")
	if code == "" {
		http.Error(w, `{"error":"missing code"}`, http.StatusBadRequest)
		return
	}

	// Exchange code for access token.
	tokenResp, err := github.ExchangeCode(r.Context(), s.cfg.GitHubClientID, s.cfg.GitHubClientSecret, code)
	if err != nil {
		slog.Error("exchanging OAuth code", "error", err)
		http.Error(w, `{"error":"OAuth exchange failed"}`, http.StatusBadGateway)
		return
	}

	// Fetch GitHub user profile.
	ghUser, err := github.GetUser(r.Context(), tokenResp.AccessToken)
	if err != nil {
		slog.Error("fetching GitHub user", "error", err)
		http.Error(w, `{"error":"failed to fetch user"}`, http.StatusBadGateway)
		return
	}

	// Upsert user in database.
	user := &models.User{
		GitHubID:  ghUser.ID,
		Login:     ghUser.Login,
		Name:      ghUser.Name,
		AvatarURL: ghUser.AvatarURL,
	}
	user, err = s.store.UpsertUser(r.Context(), user)
	if err != nil {
		slog.Error("upserting user", "error", err)
		http.Error(w, `{"error":"database error"}`, http.StatusInternalServerError)
		return
	}

	// Encrypt and store the OAuth token.
	encrypted, err := auth.Encrypt([]byte(tokenResp.AccessToken), s.cfg.EncryptionKey)
	if err != nil {
		slog.Error("encrypting token", "error", err)
		http.Error(w, `{"error":"encryption error"}`, http.StatusInternalServerError)
		return
	}
	if err := s.store.UpsertToken(r.Context(), user.ID, encrypted, tokenResp.TokenType, tokenResp.Scope); err != nil {
		slog.Error("storing token", "error", err)
		http.Error(w, `{"error":"database error"}`, http.StatusInternalServerError)
		return
	}

	// Create JWT session.
	session := &models.Session{
		UserID:    user.ID,
		Login:     user.Login,
		AvatarURL: user.AvatarURL,
	}
	jwt, err := auth.CreateToken(session, s.cfg.SessionSecret)
	if err != nil {
		slog.Error("creating session token", "error", err)
		http.Error(w, `{"error":"session error"}`, http.StatusInternalServerError)
		return
	}

	http.SetCookie(w, auth.SessionCookie(jwt))

	// Redirect to the frontend dashboard.
	http.Redirect(w, r, s.cfg.FrontendURL+"/", http.StatusTemporaryRedirect)
}

// handleLogout clears the session cookie.
func (s *Server) handleLogout(w http.ResponseWriter, r *http.Request) {
	http.SetCookie(w, auth.ClearSessionCookie())
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"logged out"}`))
}

// handleMe returns the current authenticated user.
func (s *Server) handleMe(w http.ResponseWriter, r *http.Request) {
	claims := ClaimsFromContext(r.Context())
	if claims == nil {
		http.Error(w, `{"error":"unauthorized"}`, http.StatusUnauthorized)
		return
	}

	user, err := s.store.GetUserByID(r.Context(), claims.UserID)
	if err != nil {
		slog.Error("fetching user", "error", err)
		http.Error(w, `{"error":"user not found"}`, http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(user)
}
