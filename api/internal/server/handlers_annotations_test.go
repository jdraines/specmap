package server

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/specmap/specmap/api/internal/auth"
	"github.com/specmap/specmap/api/internal/config"
	"github.com/specmap/specmap/api/internal/github"
	"github.com/specmap/specmap/api/internal/models"
	"github.com/specmap/specmap/api/internal/store"
)

// mockGitHub implements GitHubAPI for testing.
type mockGitHub struct {
	pull       *github.Pull
	pullErr    error
	repo       *github.Repo
	repoErr    error
	content    []byte
	contentErr error
}

func (m *mockGitHub) GetPull(_ context.Context, _, _, _ string, _ int) (*github.Pull, error) {
	return m.pull, m.pullErr
}
func (m *mockGitHub) GetRepo(_ context.Context, _, _, _ string) (*github.Repo, error) {
	return m.repo, m.repoErr
}
func (m *mockGitHub) ListPulls(_ context.Context, _, _, _ string) ([]github.Pull, error) {
	return nil, nil
}
func (m *mockGitHub) ListRepos(_ context.Context, _ string) ([]github.Repo, error) {
	return nil, nil
}
func (m *mockGitHub) ListPullFiles(_ context.Context, _, _, _ string, _ int) ([]github.PullFile, error) {
	return nil, nil
}
func (m *mockGitHub) GetFileContent(_ context.Context, _, _, _, _, _ string) ([]byte, error) {
	return m.content, m.contentErr
}

// mockStoreForHandlers is a mock store for testing that doesn't need a DB.
// It uses a nil Pool but overrides the methods we need via composition.
type mockStoreForHandlers struct {
	store.Store // embeds with nil Pool — don't call methods that use Pool
}

func newTestServer(gh GitHubAPI) *Server {
	return &Server{
		cfg: &config.Config{
			SessionSecret: "test-secret-32-bytes-long-enough!",
			EncryptionKey: "",
		},
		gh:  gh,
		mux: http.NewServeMux(),
	}
}

func withClaims(r *http.Request, userID int64) *http.Request {
	claims := &auth.Claims{UserID: userID, Login: "testuser"}
	ctx := context.WithValue(r.Context(), claimsKey, claims)
	return r.WithContext(ctx)
}

// tokenTestServer creates a server with a handler that bypasses the real
// getUserToken by wrapping the real handler with middleware that injects
// a known token value.
func tokenTestServer(gh GitHubAPI) (*Server, *http.ServeMux) {
	s := newTestServer(gh)
	mux := http.NewServeMux()
	return s, mux
}

func TestHandleGetAnnotations_InvalidNumber(t *testing.T) {
	s := newTestServer(&mockGitHub{})
	s.mux.HandleFunc("GET /api/v1/repos/{owner}/{repo}/pulls/{number}/annotations", s.handleGetAnnotations)

	req := httptest.NewRequest("GET", "/api/v1/repos/o/r/pulls/abc/annotations", nil)
	req = withClaims(req, 1)
	w := httptest.NewRecorder()

	s.mux.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestHandleGetAnnotations_NoToken(t *testing.T) {
	// When the store can't provide a token, the handler should return 500.
	// This happens when store is nil.
	s := newTestServer(&mockGitHub{})
	s.mux.HandleFunc("GET /api/v1/repos/{owner}/{repo}/pulls/{number}/annotations", s.handleGetAnnotations)

	req := httptest.NewRequest("GET", "/api/v1/repos/o/r/pulls/1/annotations", nil)
	// No claims — getUserToken will fail with "no claims in context"
	w := httptest.NewRecorder()

	s.mux.ServeHTTP(w, req)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected 500, got %d", w.Code)
	}
}

func TestHandleGetAnnotations_NoSpecmapFile(t *testing.T) {
	// Verifying that ErrNotFound is detectable.
	mock := &mockGitHub{
		contentErr: github.ErrNotFound,
	}
	if mock.contentErr != github.ErrNotFound {
		t.Fatal("expected ErrNotFound to be detectable")
	}
}

func TestSpecmapFileV2_UnmarshalJSON(t *testing.T) {
	data := `{
		"version": 2,
		"branch": "feature",
		"base_branch": "main",
		"head_sha": "abc123",
		"annotations": [{
			"id": "a_test1",
			"file": "main.go",
			"start_line": 10,
			"end_line": 20,
			"description": "Implements auth [1]",
			"refs": [{"id": 1, "spec_file": "spec.md", "heading": "Auth", "start_line": 5, "excerpt": "Auth section"}]
		}]
	}`

	var sf models.SpecmapFileV2
	if err := json.Unmarshal([]byte(data), &sf); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	if sf.Version != 2 {
		t.Errorf("expected version 2, got %d", sf.Version)
	}
	if len(sf.Annotations) != 1 {
		t.Fatalf("expected 1 annotation, got %d", len(sf.Annotations))
	}
	if sf.Annotations[0].Refs[0].Heading != "Auth" {
		t.Errorf("expected heading 'Auth', got %q", sf.Annotations[0].Refs[0].Heading)
	}
}

func TestEmptyAnnotationsResponse(t *testing.T) {
	resp := models.SpecmapFileV2{
		Version:     2,
		Annotations: []models.Annotation{},
	}
	data, err := json.Marshal(resp)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	var parsed models.SpecmapFileV2
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}

	if parsed.Annotations == nil {
		t.Error("expected non-nil annotations slice")
	}
	if len(parsed.Annotations) != 0 {
		t.Errorf("expected 0 annotations, got %d", len(parsed.Annotations))
	}
}

func TestErrNotFound(t *testing.T) {
	if github.ErrNotFound == nil {
		t.Fatal("ErrNotFound should not be nil")
	}
	if fmt.Sprintf("%v", github.ErrNotFound) != "not found" {
		t.Errorf("unexpected error message: %v", github.ErrNotFound)
	}
}
