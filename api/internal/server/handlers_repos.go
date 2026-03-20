package server

import (
	"log/slog"
	"net/http"

	"github.com/specmap/specmap/api/internal/github"
	"github.com/specmap/specmap/api/internal/models"
)

// handleListRepos lists repositories the authenticated user has access to.
// Fetches from GitHub API using the user's OAuth token, caches in DB.
func (s *Server) handleListRepos(w http.ResponseWriter, r *http.Request) {
	token, err := s.getUserToken(r.Context())
	if err != nil {
		slog.Error("getting user token", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to get GitHub token")
		return
	}

	ghRepos, err := github.ListRepos(r.Context(), token)
	if err != nil {
		slog.Error("listing GitHub repos", "error", err)
		writeError(w, http.StatusBadGateway, "failed to fetch repos from GitHub")
		return
	}

	// Upsert each repo in DB and build response.
	repos := make([]models.Repository, 0, len(ghRepos))
	for _, gr := range ghRepos {
		repo := &models.Repository{
			GitHubID: gr.ID,
			Owner:    gr.Owner.Login,
			Name:     gr.Name,
			FullName: gr.FullName,
			Private:  gr.Private,
		}
		repo, err = s.store.UpsertRepo(r.Context(), repo)
		if err != nil {
			slog.Error("upserting repo", "repo", gr.FullName, "error", err)
			continue
		}
		repos = append(repos, *repo)
	}

	writeJSON(w, http.StatusOK, repos)
}

// handleGetRepo fetches a single repository by owner/name.
func (s *Server) handleGetRepo(w http.ResponseWriter, r *http.Request) {
	owner := r.PathValue("owner")
	repo := r.PathValue("repo")

	token, err := s.getUserToken(r.Context())
	if err != nil {
		slog.Error("getting user token", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to get GitHub token")
		return
	}

	ghRepo, err := github.GetRepo(r.Context(), token, owner, repo)
	if err != nil {
		slog.Error("fetching GitHub repo", "owner", owner, "repo", repo, "error", err)
		writeError(w, http.StatusNotFound, "repository not found")
		return
	}

	// Upsert in DB.
	repoModel := &models.Repository{
		GitHubID: ghRepo.ID,
		Owner:    ghRepo.Owner.Login,
		Name:     ghRepo.Name,
		FullName: ghRepo.FullName,
		Private:  ghRepo.Private,
	}
	repoModel, err = s.store.UpsertRepo(r.Context(), repoModel)
	if err != nil {
		slog.Error("upserting repo", "error", err)
		writeError(w, http.StatusInternalServerError, "database error")
		return
	}

	writeJSON(w, http.StatusOK, repoModel)
}
