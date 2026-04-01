package server

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/specmap/specmap/api/internal/config"
	"github.com/specmap/specmap/api/internal/store"
)

func newWebhookTestServer(secret string) *Server {
	return &Server{
		cfg: &config.Config{
			GitHubWebhookSecret: secret,
		},
		store: &store.Store{}, // nil pool — tests use "ping" event which doesn't touch DB
		mux:   http.NewServeMux(),
	}
}

func signPayload(secret, body string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(body))
	return "sha256=" + hex.EncodeToString(mac.Sum(nil))
}

func TestHandleWebhook_ValidSignature(t *testing.T) {
	secret := "test-webhook-secret"
	s := newWebhookTestServer(secret)
	s.mux.HandleFunc("POST /api/v1/webhooks/github", s.handleWebhook)

	body := `{"action":"created","installation":{"id":1,"account":{"login":"testuser","type":"User"},"repository_selection":"all"}}`
	req := httptest.NewRequest("POST", "/api/v1/webhooks/github", strings.NewReader(body))
	req.Header.Set("X-Hub-Signature-256", signPayload(secret, body))
	req.Header.Set("X-GitHub-Event", "ping")

	w := httptest.NewRecorder()
	s.mux.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

func TestHandleWebhook_InvalidSignature(t *testing.T) {
	s := newWebhookTestServer("correct-secret")
	s.mux.HandleFunc("POST /api/v1/webhooks/github", s.handleWebhook)

	body := `{"action":"created"}`
	req := httptest.NewRequest("POST", "/api/v1/webhooks/github", strings.NewReader(body))
	req.Header.Set("X-Hub-Signature-256", signPayload("wrong-secret", body))
	req.Header.Set("X-GitHub-Event", "installation")

	w := httptest.NewRecorder()
	s.mux.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d: %s", w.Code, w.Body.String())
	}
}

func TestHandleWebhook_MissingSignature(t *testing.T) {
	s := newWebhookTestServer("some-secret")
	s.mux.HandleFunc("POST /api/v1/webhooks/github", s.handleWebhook)

	body := `{"action":"created"}`
	req := httptest.NewRequest("POST", "/api/v1/webhooks/github", strings.NewReader(body))
	req.Header.Set("X-GitHub-Event", "installation")
	// No signature header

	w := httptest.NewRecorder()
	s.mux.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Errorf("expected 401, got %d: %s", w.Code, w.Body.String())
	}
}

func TestVerifyWebhookSignature(t *testing.T) {
	s := &Server{cfg: &config.Config{GitHubWebhookSecret: "mysecret"}}

	body := []byte("hello world")
	mac := hmac.New(sha256.New, []byte("mysecret"))
	mac.Write(body)
	validSig := "sha256=" + hex.EncodeToString(mac.Sum(nil))

	tests := []struct {
		name      string
		signature string
		want      bool
	}{
		{"valid", validSig, true},
		{"wrong secret", signPayload("other", "hello world"), false},
		{"no prefix", hex.EncodeToString(mac.Sum(nil)), false},
		{"empty", "", false},
		{"garbage", "sha256=notvalidhex!", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := s.verifyWebhookSignature(body, tt.signature)
			if got != tt.want {
				t.Errorf("verifyWebhookSignature() = %v, want %v", got, tt.want)
			}
		})
	}
}
