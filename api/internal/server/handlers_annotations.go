package server

import (
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"strconv"

	"github.com/specmap/specmap/api/internal/github"
	"github.com/specmap/specmap/api/internal/models"
)

// handleGetAnnotations returns specmap annotations for a pull request.
// GET /api/v1/repos/{owner}/{repo}/pulls/{number}/annotations
func (s *Server) handleGetAnnotations(w http.ResponseWriter, r *http.Request) {
	owner := r.PathValue("owner")
	repo := r.PathValue("repo")
	numberStr := r.PathValue("number")

	number, err := strconv.Atoi(numberStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid pull request number")
		return
	}

	token, err := s.getUserToken(r.Context())
	if err != nil {
		slog.Error("getting user token", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to get GitHub token")
		return
	}

	// Fetch PR from GitHub to get head_sha and head_branch.
	ghPull, err := s.gh.GetPull(r.Context(), token, owner, repo, number)
	if err != nil {
		slog.Error("fetching GitHub pull", "error", err)
		writeError(w, http.StatusNotFound, "pull request not found")
		return
	}

	// Ensure repo exists in DB.
	ghRepo, err := s.gh.GetRepo(r.Context(), token, owner, repo)
	if err != nil {
		slog.Error("fetching repo", "error", err)
		writeError(w, http.StatusNotFound, "repository not found")
		return
	}
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

	// Upsert PR.
	pr := &models.PullRequest{
		RepositoryID: repoModel.ID,
		Number:       ghPull.Number,
		Title:        ghPull.Title,
		State:        ghPull.State,
		HeadBranch:   ghPull.Head.Ref,
		BaseBranch:   ghPull.Base.Ref,
		HeadSHA:      ghPull.Head.SHA,
		AuthorLogin:  ghPull.User.Login,
	}
	pr, err = s.store.UpsertPull(r.Context(), pr)
	if err != nil {
		slog.Error("upserting pull", "error", err)
		writeError(w, http.StatusInternalServerError, "database error")
		return
	}

	// Check mapping cache.
	cached, err := s.store.GetMappingCache(r.Context(), pr.ID, pr.HeadSHA)
	if err != nil {
		slog.Error("checking mapping cache", "error", err)
		writeError(w, http.StatusInternalServerError, "database error")
		return
	}

	if cached != nil {
		var specmap models.SpecmapFileV2
		if err := json.Unmarshal(cached.SpecmapJSON, &specmap); err != nil {
			slog.Error("parsing cached specmap", "error", err)
			writeError(w, http.StatusInternalServerError, "corrupt cache data")
			return
		}
		writeJSON(w, http.StatusOK, specmap)
		return
	}

	// Cache miss — fetch .specmap/{head_branch}.json from the repo.
	specmapPath := fmt.Sprintf(".specmap/%s.json", pr.HeadBranch)
	content, err := s.gh.GetFileContent(r.Context(), token, owner, repo, specmapPath, pr.HeadSHA)
	if err != nil {
		if errors.Is(err, github.ErrNotFound) {
			writeJSON(w, http.StatusOK, models.SpecmapFileV2{
				Version:     2,
				Annotations: []models.Annotation{},
			})
			return
		}
		slog.Error("fetching specmap file", "path", specmapPath, "error", err)
		writeError(w, http.StatusBadGateway, "failed to fetch specmap file from GitHub")
		return
	}

	var specmap models.SpecmapFileV2
	if err := json.Unmarshal(content, &specmap); err != nil {
		slog.Error("parsing specmap file", "error", err)
		writeError(w, http.StatusUnprocessableEntity, "invalid specmap file format")
		return
	}

	// Cache for future requests.
	mc := &models.MappingCache{
		PullRequestID: pr.ID,
		HeadSHA:       pr.HeadSHA,
		SpecmapJSON:   content,
	}
	if _, err := s.store.UpsertMappingCache(r.Context(), mc); err != nil {
		slog.Error("caching specmap", "error", err)
	}

	writeJSON(w, http.StatusOK, specmap)
}
