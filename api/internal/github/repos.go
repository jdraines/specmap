package github

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

const reposAPIURL = "https://api.github.com/user/repos"

// Repo is the relevant fields from GitHub's repos API.
type Repo struct {
	ID       int64     `json:"id"`
	Name     string    `json:"name"`
	FullName string    `json:"full_name"`
	Owner    RepoOwner `json:"owner"`
	Private  bool      `json:"private"`
	HTMLURL  string    `json:"html_url"`
}

// RepoOwner is the owner field in a GitHub repo response.
type RepoOwner struct {
	Login string `json:"login"`
}

// ListRepos lists repositories the authenticated user has access to.
// Returns up to 100 repos sorted by most recently pushed.
func ListRepos(ctx context.Context, accessToken string) ([]Repo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		reposAPIURL+"?sort=pushed&per_page=100", nil)
	if err != nil {
		return nil, fmt.Errorf("creating repos request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching repos: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub repos API failed (%d): %s", resp.StatusCode, body)
	}

	var repos []Repo
	if err := json.NewDecoder(resp.Body).Decode(&repos); err != nil {
		return nil, fmt.Errorf("parsing repos response: %w", err)
	}

	return repos, nil
}

// GetRepo fetches a single repository by owner/name.
func GetRepo(ctx context.Context, accessToken, owner, name string) (*Repo, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/%s", owner, name)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating repo request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching repo: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, fmt.Errorf("repository %s/%s not found", owner, name)
	}
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub repo API failed (%d): %s", resp.StatusCode, body)
	}

	var repo Repo
	if err := json.NewDecoder(resp.Body).Decode(&repo); err != nil {
		return nil, fmt.Errorf("parsing repo response: %w", err)
	}

	return &repo, nil
}
