package server

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/specmap/specmap/api/internal/auth"
)

// getUserToken decrypts the authenticated user's GitHub OAuth token.
func (s *Server) getUserToken(ctx context.Context) (string, error) {
	claims := ClaimsFromContext(ctx)
	if claims == nil {
		return "", fmt.Errorf("no claims in context")
	}

	encrypted, err := s.store.GetToken(ctx, claims.UserID)
	if err != nil {
		return "", fmt.Errorf("getting encrypted token: %w", err)
	}

	plaintext, err := auth.Decrypt(encrypted, s.cfg.EncryptionKey)
	if err != nil {
		return "", fmt.Errorf("decrypting token: %w", err)
	}

	return string(plaintext), nil
}

// writeJSON writes a JSON response with the given status code.
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

// writeError writes a JSON error response.
func writeError(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}
