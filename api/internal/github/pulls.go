package github

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
)

// Pull is the relevant fields from GitHub's pulls API.
type Pull struct {
	Number  int       `json:"number"`
	Title   string    `json:"title"`
	State   string    `json:"state"`
	HTMLURL string    `json:"html_url"`
	Head    PullRef   `json:"head"`
	Base    PullRef   `json:"base"`
	User    PullUser  `json:"user"`
}

// PullRef is a branch reference in a PR.
type PullRef struct {
	Ref string `json:"ref"`
	SHA string `json:"sha"`
}

// PullUser is the author of a PR.
type PullUser struct {
	Login string `json:"login"`
}

// PullFile is a file changed in a PR.
type PullFile struct {
	Filename  string `json:"filename"`
	Status    string `json:"status"` // added, removed, modified, renamed
	Additions int    `json:"additions"`
	Deletions int    `json:"deletions"`
	Changes   int    `json:"changes"`
	Patch     string `json:"patch"`
}

// ListPulls lists open pull requests for a repository.
func ListPulls(ctx context.Context, accessToken, owner, repo string) ([]Pull, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/%s/pulls?state=open&per_page=30", owner, repo)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating pulls request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching pulls: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub pulls API failed (%d): %s", resp.StatusCode, body)
	}

	var pulls []Pull
	if err := json.NewDecoder(resp.Body).Decode(&pulls); err != nil {
		return nil, fmt.Errorf("parsing pulls response: %w", err)
	}

	return pulls, nil
}

// GetPull fetches a single pull request.
func GetPull(ctx context.Context, accessToken, owner, repo string, number int) (*Pull, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/%s/pulls/%d", owner, repo, number)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating pull request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching pull: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, fmt.Errorf("pull request %s/%s#%d not found", owner, repo, number)
	}
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub pull API failed (%d): %s", resp.StatusCode, body)
	}

	var pull Pull
	if err := json.NewDecoder(resp.Body).Decode(&pull); err != nil {
		return nil, fmt.Errorf("parsing pull response: %w", err)
	}

	return &pull, nil
}

// ListPullFiles lists files changed in a pull request.
func ListPullFiles(ctx context.Context, accessToken, owner, repo string, number int) ([]PullFile, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/%s/pulls/%d/files?per_page=100", owner, repo, number)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating pull files request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching pull files: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub pull files API failed (%d): %s", resp.StatusCode, body)
	}

	var files []PullFile
	if err := json.NewDecoder(resp.Body).Decode(&files); err != nil {
		return nil, fmt.Errorf("parsing pull files response: %w", err)
	}

	return files, nil
}
