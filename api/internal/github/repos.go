package github

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

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

// Installation is a GitHub App installation.
type Installation struct {
	ID int64 `json:"id"`
}

// installationReposResponse wraps the paginated repos list from the installations API.
type installationReposResponse struct {
	Repositories []Repo `json:"repositories"`
}

// ListInstallations returns the GitHub App installations accessible to the authenticated user.
func ListInstallations(ctx context.Context, accessToken string) ([]Installation, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		"https://api.github.com/user/installations?per_page=100", nil)
	if err != nil {
		return nil, fmt.Errorf("creating installations request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching installations: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub installations API failed (%d): %s", resp.StatusCode, body)
	}

	var result struct {
		Installations []Installation `json:"installations"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("parsing installations response: %w", err)
	}

	return result.Installations, nil
}

// ListRepos lists repositories accessible to the authenticated user via GitHub App installations.
// It queries each installation for its repositories and aggregates the results.
// Returns an empty list (no error) if no installations are found.
func ListRepos(ctx context.Context, accessToken string) ([]Repo, error) {
	installations, err := ListInstallations(ctx, accessToken)
	if err != nil {
		return nil, fmt.Errorf("listing installations: %w", err)
	}

	if len(installations) == 0 {
		return []Repo{}, nil
	}

	var allRepos []Repo
	for _, inst := range installations {
		repos, err := listInstallationRepos(ctx, accessToken, inst.ID)
		if err != nil {
			return nil, fmt.Errorf("listing repos for installation %d: %w", inst.ID, err)
		}
		allRepos = append(allRepos, repos...)
	}

	return allRepos, nil
}

// listInstallationRepos fetches repositories for a specific installation.
func listInstallationRepos(ctx context.Context, accessToken string, installationID int64) ([]Repo, error) {
	url := fmt.Sprintf("https://api.github.com/user/installations/%d/repositories?per_page=100", installationID)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating installation repos request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching installation repos: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub installation repos API failed (%d): %s", resp.StatusCode, body)
	}

	var result installationReposResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("parsing installation repos response: %w", err)
	}

	return result.Repositories, nil
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
