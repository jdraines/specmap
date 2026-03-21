package server

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHandleGetSpecContent_InvalidNumber(t *testing.T) {
	s := newTestServer(&mockGitHub{})
	s.mux.HandleFunc("GET /api/v1/repos/{owner}/{repo}/pulls/{number}/specs/{path...}", s.handleGetSpecContent)

	req := httptest.NewRequest("GET", "/api/v1/repos/o/r/pulls/abc/specs/docs/spec.md", nil)
	req = withClaims(req, 1)
	w := httptest.NewRecorder()

	s.mux.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestHandleGetSpecContent_NoClaims(t *testing.T) {
	s := newTestServer(&mockGitHub{})
	s.mux.HandleFunc("GET /api/v1/repos/{owner}/{repo}/pulls/{number}/specs/{path...}", s.handleGetSpecContent)

	req := httptest.NewRequest("GET", "/api/v1/repos/o/r/pulls/1/specs/docs/spec.md", nil)
	// No claims in context — getUserToken returns "no claims in context".
	w := httptest.NewRecorder()

	s.mux.ServeHTTP(w, req)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", w.Code)
	}
}
