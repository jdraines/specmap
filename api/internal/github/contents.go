package github

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
)

// ErrNotFound indicates the requested resource was not found (404).
var ErrNotFound = errors.New("not found")

// contentsResponse is the relevant fields from GitHub's contents API.
type contentsResponse struct {
	Content  string `json:"content"`
	Encoding string `json:"encoding"`
}

// GetFileContent fetches a file's content from a repo at a specific git ref.
// Returns ErrNotFound on 404.
func GetFileContent(ctx context.Context, accessToken, owner, repo, path, ref string) ([]byte, error) {
	apiURL := fmt.Sprintf("https://api.github.com/repos/%s/%s/contents/%s",
		owner, repo, url.PathEscape(path))
	if ref != "" {
		apiURL += "?ref=" + url.QueryEscape(ref)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, apiURL, nil)
	if err != nil {
		return nil, fmt.Errorf("creating contents request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/vnd.github+json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching contents: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, ErrNotFound
	}
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("GitHub contents API failed (%d): %s", resp.StatusCode, body)
	}

	var cr contentsResponse
	if err := json.NewDecoder(resp.Body).Decode(&cr); err != nil {
		return nil, fmt.Errorf("parsing contents response: %w", err)
	}

	if cr.Encoding != "base64" {
		return nil, fmt.Errorf("unexpected encoding %q (expected base64)", cr.Encoding)
	}

	decoded, err := base64.StdEncoding.DecodeString(cr.Content)
	if err != nil {
		return nil, fmt.Errorf("decoding base64 content: %w", err)
	}

	return decoded, nil
}
