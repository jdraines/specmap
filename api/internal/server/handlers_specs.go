package server

import (
	"errors"
	"log/slog"
	"net/http"
	"strconv"

	"github.com/specmap/specmap/api/internal/github"
)

// handleGetSpecContent returns the content of a spec file at the PR's head SHA.
// GET /api/v1/repos/{owner}/{repo}/pulls/{number}/specs/{path...}
func (s *Server) handleGetSpecContent(w http.ResponseWriter, r *http.Request) {
	owner := r.PathValue("owner")
	repo := r.PathValue("repo")
	numberStr := r.PathValue("number")
	specPath := r.PathValue("path")

	number, err := strconv.Atoi(numberStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid pull request number")
		return
	}

	if specPath == "" {
		writeError(w, http.StatusBadRequest, "missing spec path")
		return
	}

	token, err := s.getUserToken(r.Context())
	if err != nil {
		slog.Error("getting user token", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to get GitHub token")
		return
	}

	ghPull, err := s.gh.GetPull(r.Context(), token, owner, repo, number)
	if err != nil {
		slog.Error("fetching GitHub pull", "error", err)
		writeError(w, http.StatusNotFound, "pull request not found")
		return
	}

	content, err := s.gh.GetFileContent(r.Context(), token, owner, repo, specPath, ghPull.Head.SHA)
	if err != nil {
		if errors.Is(err, github.ErrNotFound) {
			writeError(w, http.StatusNotFound, "spec file not found")
			return
		}
		slog.Error("fetching spec content", "path", specPath, "error", err)
		writeError(w, http.StatusBadGateway, "failed to fetch spec file from GitHub")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"path":    specPath,
		"content": string(content),
	})
}
