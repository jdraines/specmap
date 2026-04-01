package server

import (
	"errors"
	"log/slog"
	"net/http"
	"strconv"

	"github.com/specmap/specmap/api/internal/github"
	"github.com/specmap/specmap/api/internal/models"
)

// handleListPulls lists open pull requests for a repository.
func (s *Server) handleListPulls(w http.ResponseWriter, r *http.Request) {
	owner := r.PathValue("owner")
	repo := r.PathValue("repo")

	token, err := s.getUserToken(r.Context())
	if err != nil {
		slog.Error("getting user token", "error", err)
		writeError(w, http.StatusInternalServerError, "failed to get GitHub token")
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

	// Fetch PRs from GitHub.
	ghPulls, err := s.gh.ListPulls(r.Context(), token, owner, repo)
	if err != nil {
		slog.Error("listing GitHub pulls", "error", err)
		writeError(w, http.StatusBadGateway, "failed to fetch pull requests from GitHub")
		return
	}

	// Upsert each PR in DB.
	pulls := make([]models.PullRequest, 0, len(ghPulls))
	for _, gp := range ghPulls {
		pr := &models.PullRequest{
			RepositoryID: repoModel.ID,
			Number:       gp.Number,
			Title:        gp.Title,
			State:        gp.State,
			HeadBranch:   gp.Head.Ref,
			BaseBranch:   gp.Base.Ref,
			HeadSHA:      gp.Head.SHA,
			AuthorLogin:  gp.User.Login,
		}
		pr, err = s.store.UpsertPull(r.Context(), pr)
		if err != nil {
			slog.Error("upserting pull", "number", gp.Number, "error", err)
			continue
		}
		pulls = append(pulls, *pr)
	}

	writeJSON(w, http.StatusOK, pulls)
}

// handleGetPull fetches a single pull request by number.
func (s *Server) handleGetPull(w http.ResponseWriter, r *http.Request) {
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

	ghPull, err := s.gh.GetPull(r.Context(), token, owner, repo, number)
	if err != nil {
		slog.Error("fetching GitHub pull", "error", err)
		writeError(w, http.StatusNotFound, "pull request not found")
		return
	}

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

	writeJSON(w, http.StatusOK, pr)
}

// handleGetPullFiles returns the list of files changed in a pull request.
func (s *Server) handleGetPullFiles(w http.ResponseWriter, r *http.Request) {
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

	files, err := s.gh.ListPullFiles(r.Context(), token, owner, repo, number)
	if err != nil {
		slog.Error("listing pull files", "error", err)
		writeError(w, http.StatusBadGateway, "failed to fetch pull request files")
		return
	}

	writeJSON(w, http.StatusOK, files)
}

// handleGetFileSource returns the full content of a file at the PR's base branch ref.
// GET /api/v1/repos/{owner}/{repo}/pulls/{number}/file-source?path=...
func (s *Server) handleGetFileSource(w http.ResponseWriter, r *http.Request) {
	owner := r.PathValue("owner")
	repo := r.PathValue("repo")
	numberStr := r.PathValue("number")
	filePath := r.URL.Query().Get("path")

	number, err := strconv.Atoi(numberStr)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid pull request number")
		return
	}

	if filePath == "" {
		writeError(w, http.StatusBadRequest, "missing path parameter")
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

	content, err := s.gh.GetFileContent(r.Context(), token, owner, repo, filePath, ghPull.Base.Ref)
	if err != nil {
		if errors.Is(err, github.ErrNotFound) {
			writeError(w, http.StatusNotFound, "file not found at base branch")
			return
		}
		slog.Error("fetching file source", "path", filePath, "error", err)
		writeError(w, http.StatusBadGateway, "failed to fetch file from GitHub")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"content": string(content),
	})
}
